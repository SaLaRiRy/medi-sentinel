"""患者侧 AI 问诊 HTTP 接口（`SPEC.md` 5.4「AI 问诊与知识库」）。

- `POST /chat/send`：一次问诊，以 SSE 流式返回（SPEC.md 5.5）
- `GET /chat/sessions`：本人会话列表，按更新时间倒序
- `GET /chat/sessions/{id}/messages`：指定会话的历史消息（仅按会话号过滤）

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
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import (
    Principal,
    get_session,
    require_admin,
    require_patient,
    resolve_optional_principal,
)
from core.errors import ApiError
from core.response import (
    JSON_MEDIA_TYPE,
    Envelope,
    PagePayload,
    error_responses,
    page_result,
    success,
)
from core.serialization import ApiDateTime
from models.consult import ConsultMessageRow, ConsultSessionRow
from repositories.consult import ConsultRepository
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


class SessionView(BaseModel):
    id: int
    title: str
    message_count: int
    create_time: ApiDateTime | None = None
    update_time: ApiDateTime | None = None

    @classmethod
    def of(cls, row: ConsultSessionRow) -> "SessionView":
        return cls(
            id=row.id,
            title=row.title,
            message_count=row.message_count or 0,
            create_time=row.create_time,
            update_time=row.update_time,
        )


class MessageView(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    references: list[dict] = []
    graph: list[dict] = []
    cost_time: int | None = None
    create_time: ApiDateTime | None = None

    @classmethod
    def of(cls, row: ConsultMessageRow) -> "MessageView":
        return cls(
            id=row.id,
            session_id=row.session_id,
            role=row.role,
            content=row.content,
            references=_parse_json_list(row.references_json),
            graph=_parse_json_list(row.graph_json),
            cost_time=row.cost_time,
            create_time=row.create_time,
        )


def _parse_json_list(raw: str | None) -> list[dict]:
    """A stored JSON column, or `[]` when the message carries none."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def sse_frame(frame: dict) -> str:
    """One frame is `data: <JSON>\\n\\n`; the type is the JSON field, not `event:`."""
    return f"data: {json.dumps(frame, ensure_ascii=False)}\n\n"


@router.post(
    "/chat/send",
    response_class=EventStreamResponse,
    responses=error_responses(
        401, 403, 409, 422, 503, 504, media_type=JSON_MEDIA_TYPE
    ),
)
async def send_chat(request: Request, payload: ChatRequest) -> EventStreamResponse:
    database = request.app.state.database
    ports: OrchestrationPorts = request.app.state.orchestration_ports
    guard: SessionGenerationGuard = request.app.state.generation_guard
    # A token attributes the session to its holder; no token stays anonymous so
    # the pre-auth callers (007-011) keep their behaviour (TICKET-014).
    principal = await resolve_optional_principal(request)
    user_id = principal.user_id if principal is not None else None

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


@router.get(
    "/chat/sessions",
    response_model=Envelope[list[SessionView]],
    responses=error_responses(401, 403),
)
async def list_sessions(
    principal: Principal = Depends(require_patient),
    session: AsyncSession = Depends(get_session),
) -> Envelope[list[SessionView]]:
    rows = await ConsultRepository(session).list_sessions(user_id=principal.user_id)
    return success([SessionView.of(row) for row in rows])


@router.get(
    "/chat/admin/sessions",
    response_model=Envelope[PagePayload[SessionView]],
    responses=error_responses(401, 403, 422),
)
async def admin_sessions(
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Envelope[PagePayload[SessionView]]:
    """管理员查看全部患者的会话（SPEC.md 5.4「AI 问诊与知识库」）。"""
    rows, total = await ConsultRepository(session).list_sessions_page(
        offset=(page - 1) * page_size, limit=page_size
    )
    return page_result(
        [SessionView.of(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/chat/sessions/{session_id}/messages",
    response_model=Envelope[list[MessageView]],
    responses=error_responses(401, 403, 404),
)
async def list_messages(
    session_id: int,
    principal: Principal = Depends(require_patient),
    session: AsyncSession = Depends(get_session),
) -> Envelope[list[MessageView]]:
    repository = ConsultRepository(session)
    if await repository.find_session_by_id(session_id) is None:
        raise ApiError(404, "会话不存在")
    rows = await repository.messages(session_id)
    return success([MessageView.of(row) for row in rows])


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
    safety: dict | None = None
    done: dict | None = None
    try:
        async for frame in orchestrator.run(
            payload, session_id=opened.session_id, history=tuple(opened.history)
        ):
            if frame["type"] == "content":
                answer.append(frame["content"])
            elif frame["type"] == "safety":
                safety = frame
            elif frame["type"] == "done":
                done = frame
            yield sse_frame(frame)
    finally:
        try:
            # Shielded: a disconnect cancels this task at the `yield` above, and
            # the settle must still run to completion (TICKET-010).
            with anyio.CancelScope(shield=True):
                await _commit_turn(
                    session,
                    sink=sink,
                    opened=opened,
                    answer=answer,
                    safety=safety,
                    done=done,
                )
        finally:
            guard.release(key)


async def _commit_turn(
    session: AsyncSession,
    *,
    sink: InMemoryTraceSink,
    opened: OpenedTurn,
    answer: list[str],
    safety: dict | None,
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
                answer=_assistant_content(answer=answer, safety=safety),
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


def _assistant_content(*, answer: list[str], safety: dict | None) -> str:
    """What the assistant message keeps for a finished turn.

    拦截路径没有 `content` 帧，若原样持久化就是空消息；TICKET-008 挂账第 1 条在
    本票拍板为「存安全提示」：把安全门的 `message` 与 `suggested_action` 写进历史，
    否则重新加载对话只剩一个空气泡，安全提示随流消失。放行路径仍是累计的生成全文。
    """
    if safety is not None:
        return f"{safety['message']}\n{safety['suggested_action']}"
    return "".join(answer)


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
