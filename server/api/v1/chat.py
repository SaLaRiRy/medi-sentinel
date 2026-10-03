"""`POST /api/v1/chat/send`: one consult, streamed as SSE (SPEC.md 5.5).

The route is thin on purpose: session/message rules live in `services.chat`, the
whole AI chain lives behind the B-1 entry point, and traces are buffered while
the model streams then flushed to B-4 so no database connection is held across
generation (FUNCTIONAL_SPEC 5.7).
"""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from core.deps import get_current_user_id
from repositories.trace import TraceRepository
from services.chat import OpenedTurn, close_turn, open_turn
from skills.orchestration import (
    ChatRequest,
    OrchestrationPorts,
    Orchestrator,
)
from skills.trace import InMemoryTraceSink

router = APIRouter(tags=["chat"])

SSE_MEDIA_TYPE = "text/event-stream; charset=utf-8"
SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


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

    # The user turn commits before the model is called, so a failed stream keeps
    # the question and never writes an answer (FUNCTIONAL_SPEC 5.7).
    async with database.session_factory() as session:
        opened = await open_turn(
            session, user_id=get_current_user_id(request), request=payload
        )
        await session.commit()

    sink = InMemoryTraceSink()
    orchestrator = Orchestrator(ports=ports, sink=sink)
    return EventStreamResponse(
        _stream(orchestrator, payload, opened, database=database, sink=sink),
        headers=dict(SSE_HEADERS),
    )


async def _stream(
    orchestrator: Orchestrator,
    payload: ChatRequest,
    opened: OpenedTurn,
    *,
    database,
    sink: InMemoryTraceSink,
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
        if done is not None:
            await _save_assistant_turn(
                database, session_id=opened.session_id, answer="".join(answer), done=done
            )
        await _save_trace(database, sink)


async def _save_assistant_turn(database, *, session_id: int, answer: str, done: dict) -> None:
    async with database.session_factory() as session:
        await close_turn(
            session,
            session_id=session_id,
            answer=answer,
            references=done["references"],
            candidates=done["graph"],
            cost_time=done["cost_time"],
        )
        await session.commit()


async def _save_trace(database, sink: InMemoryTraceSink) -> None:
    async with database.session_factory() as session:
        repository = TraceRepository(session)
        for span in sink.spans:
            await repository.record_span(span)
        for decision in sink.routes:
            await repository.record_route(decision)
        await session.commit()
