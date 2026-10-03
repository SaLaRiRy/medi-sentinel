"""AI 问诊的会话与消息规则（TICKET-007，`FUNCTIONAL_SPEC.md` 5.7）。

- 定位或新建会话：带 `session_id` 时按「会话号 + 本人」查找，找不到则新建；
- 用户消息在调用模型之前落库；
- 历史 = 本会话全部消息排除刚保存的那条，取最近 `HISTORY_LIMIT` 条；
- 助手消息在流完全结束后落库，且会话消息数 +2。

用户消息与助手消息各自在一个独立事务里提交：流中途失败时助手消息不写入、
用户消息保留，消息计数不增加（FUNCTIONAL_SPEC 5.7）。
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from repositories.consult import (
    USER_ROLE,
    ConsultRepository,
    session_title,
)
from skills.orchestration import HISTORY_LIMIT, ChatRequest, ChatTurn


@dataclass(frozen=True)
class OpenedTurn:
    session_id: int
    history: tuple[ChatTurn, ...]


async def open_turn(
    session: AsyncSession, *, user_id: int | None, request: ChatRequest
) -> OpenedTurn:
    repository = ConsultRepository(session)
    consult_session = None
    if request.session_id is not None:
        consult_session = await repository.find_session(
            request.session_id, user_id=user_id
        )
    if consult_session is None:
        consult_session = await repository.create_session(
            user_id=user_id, title=session_title(request.message)
        )

    message = await repository.add_message(
        consult_session.id, role=USER_ROLE, content=request.message
    )
    history = await repository.history(
        consult_session.id, exclude_message_id=message.id, limit=HISTORY_LIMIT
    )
    return OpenedTurn(
        session_id=consult_session.id,
        history=tuple(ChatTurn(role=row.role, content=row.content) for row in history),
    )


async def close_turn(
    session: AsyncSession,
    *,
    session_id: int,
    answer: str,
    references: Sequence[Mapping[str, object]],
    candidates: Sequence[Mapping[str, object]],
    cost_time: int,
) -> None:
    """Persist the assistant message and add the two messages to the count.

    The payloads are the `done` frame's own shapes: the stored references match
    the wire contract, so `distance` never leaks into storage either.
    """
    await ConsultRepository(session).complete_turn(
        session_id,
        assistant_content=answer,
        references_json=json.dumps(list(references), ensure_ascii=False),
        graph_json=json.dumps(list(candidates), ensure_ascii=False),
        cost_time=cost_time,
    )
