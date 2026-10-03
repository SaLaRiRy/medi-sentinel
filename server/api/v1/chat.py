"""`POST /api/v1/chat/send`: one consult, streamed as SSE (SPEC.md 5.5).

The route is thin on purpose: session/message rules live in `services.chat`, the
whole AI chain lives behind the B-1 entry point, and the request's single
`AsyncSession` is committed before the model is called and again after the
stream, then closed so its connection returns to the pool. Between those two
commits the connection is idle in the pool, so a long generation never holds one
(SPEC.md 3.1 / 3.3). The final settle runs shielded: a client that hangs up
cancels the streaming task, and the trace and the connection still have to be
settled instead of leaking (TICKET-010).
"""

import json
import logging
from collections.abc import AsyncIterator

import anyio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_current_user_id
from core.errors import ApiError
from repositories.trace import TraceRepository
from services.chat import OpenedTurn, close_turn, open_turn
from services.generation import GenerationKey, SessionGenerationGuard
from skills.orchestration import (
    ChatRequest,
    OrchestrationPorts,
    Orchestrator,
)
from skills.trace import InMemoryTraceSink

router = APIRouter(tags=["chat"])

SSE_MEDIA_TYPE = "text/event-stream; charset=utf-8"
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}

logger = logging.getLogger(__name__)


class EventStreamResponse(StreamingResponse):
    """Declares the SSE media type so the committed REST contract shows it."""

    media_type = SSE_MEDIA_TYPE


def sse_frame(frame: dict) -> str:
    """One frame is `data: <JSON>\\n\\n`; the type is the JSON field, not `event:`."""
    return f"data: {json.dumps(frame, ensure_ascii=False)}\n\n"


@router.post("/chat/send", response_class=EventStreamResponse)
async def send_chat(request: Request, payload: ChatRequest) -> EventStreamResponse:
    database = request.app.state.database
    ports: OrchestrationPorts = request.app.state.orchestration_ports
    guard: SessionGenerationGuard = request.app.state.generation_guard
    user_id = get_current_user_id(request)

    # One generation per session (SPEC.md 5.4 409). A brand-new session has no id
    # yet, so it cannot collide with an in-flight one.
    key = (
        None
        if payload.session_id is None
        else GenerationKey(user_id, payload.session_id)
    )
    if not guard.try_acquire(key):
        raise ApiError(409, "同一会话已有生成中的请求")

    # One session per request (SPEC.md 3.1). The user turn commits before the
    # model is called, so a failed stream keeps the question and never writes an
    # answer (FUNCTIONAL_SPEC 5.7); the commit also frees the connection for the
    # duration of the generation.
    session = database.session_factory()
    try:
        opened = await open_turn(session, user_id=user_id, request=payload)
        await session.commit()
    except BaseException:
        await _settle_session(session)
        guard.release(key)
        raise

    sink = InMemoryTraceSink()
    orchestrator = Orchestrator(ports=ports, sink=sink)
    return EventStreamResponse(
        _stream(
            orchestrator,
            payload,
            opened,
            session=session,
            sink=sink,
            guard=guard,
            key=key,
        ),
        headers=dict(SSE_HEADERS),
    )


async def _stream(
    orchestrator: Orchestrator,
    payload: ChatRequest,
    opened: OpenedTurn,
    *,
    session: AsyncSession,
    sink: InMemoryTraceSink,
    guard: SessionGenerationGuard,
    key: GenerationKey | None,
) -> AsyncIterator[str]:
    answer: list[str] = []
    done: dict | None = None
    try:
        async for frame in orchestrator.run(
            payload, session_id=opened.session_id, history=tuple(opened.history)
        ):
            if frame["type"] == "content":
                answer.append(frame["content"])
            elif frame["type"] == "done":
                done = frame
            yield sse_frame(frame)
    finally:
        try:
            # Shielded: a disconnect cancels this task at the `yield` above, and
            # the settle must still run to completion (TICKET-010).
            with anyio.CancelScope(shield=True):
                await _commit_turn(
                    session, sink=sink, opened=opened, answer=answer, done=done
                )
        finally:
            guard.release(key)


async def _commit_turn(
    session: AsyncSession,
    *,
    sink: InMemoryTraceSink,
    opened: OpenedTurn,
    answer: list[str],
    done: dict | None,
) -> None:
    """Commit the assistant turn (when the stream reached `done`) and the trace,
    then return the connection. On any failure, roll back and log: the response
    is already on the wire, so there is no one left to raise to."""
    try:
        if done is not None:
            await close_turn(
                session,
                session_id=opened.session_id,
                answer="".join(answer),
                references=done["references"],
                candidates=done["graph"],
                cost_time=done["cost_time"],
            )
        repository = TraceRepository(session)
        for span in sink.spans:
            await repository.record_span(span)
        for decision in sink.routes:
            await repository.record_route(decision)
        await session.commit()
    except Exception:
        logger.exception("failed to settle the consult turn")
        await _settle_session(session)
    else:
        await session.close()


async def _settle_session(session: AsyncSession) -> None:
    """Roll back and close, shielded so a cancelled request still releases its
    connection back to the pool (SPEC.md 3.3)."""
    with anyio.CancelScope(shield=True):
        try:
            await session.rollback()
        except Exception:
            logger.exception("failed to roll back the consult session")
        finally:
            await session.close()
