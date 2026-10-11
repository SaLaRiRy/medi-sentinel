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
from models.accounts import UserRow
from repositories.health_records import HealthRecordRepository
from skills.orchestration import HISTORY_LIMIT, ChatRequest, ChatTurn, PatientProfile

#: 档案段取最近几条既往记录（提示词的限长在 `prompt.py`，这里只决定取多少条）。
PROFILE_RECORD_LIMIT = 3


@dataclass(frozen=True)
class OpenedTurn:
    session_id: int
    history: tuple[ChatTurn, ...]
    #: 串行预取的患者档案（TICKET-AC-07）；匿名会话为 `None`。
    profile: PatientProfile | None = None


def _record_summary(record) -> str:
    """一条档案压成一行摘要：日期 + 类型 + 诊断 + 处理。"""
    row = record.row
    when = row.visit_date or (row.create_time.date() if row.create_time else None)
    parts = [row.record_type or "就诊记录"]
    if row.diagnosis:
        parts.append(f"诊断 {row.diagnosis}")
    if row.treatment:
        parts.append(f"处理 {row.treatment}")
    joined = "，".join(parts)
    return f"{when} {joined}" if when else joined


async def load_patient_profile(
    session: AsyncSession, *, user_id: int | None
) -> PatientProfile | None:
    """串行读一次本人的档案（TICKET-AC-07）。

    刻意**不**新增端口：调用点在 `open_turn` 里，与 `history` 一样是**串行预取传值**
    （`orchestrator.run(..., profile=...)`），因此 `OrchestrationPorts` 的构造点、
    `gather` 的位置索引与回放 FIFO 全都不受影响。
    """
    if user_id is None:
        return None
    user = await session.get(UserRow, user_id)
    if user is None:
        return None
    records = await HealthRecordRepository(session).list_for_user(user_id)
    return PatientProfile(
        allergy_history=(user.allergy_history or None),
        records=tuple(
            _record_summary(record) for record in records[:PROFILE_RECORD_LIMIT]
        ),
    )


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
        profile=await load_patient_profile(session, user_id=user_id),
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
