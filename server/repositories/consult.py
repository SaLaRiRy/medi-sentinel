"""B-5: async storage for AI consult sessions and messages (TICKET-007).

The session owns the transaction: nothing here commits, so a turn's writes land
or roll back with the session the caller opened.
"""

from sqlalchemy import select

from models.consult import DEFAULT_TITLE, ConsultMessageRow, ConsultSessionRow
from repositories.base import Repository

USER_ROLE = "user"
ASSISTANT_ROLE = "assistant"


def session_title(message: str) -> str:
    """首条消息前 20 字符；超过 20 字符时末尾追加 `...`（FUNCTIONAL_SPEC 5.7）。"""
    if len(message) > 20:
        return message[:20] + "..."
    return message


class ConsultRepository(Repository):
    async def find_session(
        self, session_id: int, *, user_id: int | None
    ) -> ConsultSessionRow | None:
        """会话号 + 本人；不匹配（含属于他人）时返回 `None`，由调用方新建。"""
        criteria = [ConsultSessionRow.id == session_id]
        if user_id is None:
            criteria.append(ConsultSessionRow.user_id.is_(None))
        else:
            criteria.append(ConsultSessionRow.user_id == user_id)
        return (
            await self._session.execute(select(ConsultSessionRow).where(*criteria))
        ).scalar_one_or_none()

    async def create_session(
        self, *, user_id: int | None, title: str = DEFAULT_TITLE
    ) -> ConsultSessionRow:
        row = ConsultSessionRow(user_id=user_id, title=title, message_count=0)
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_sessions(self, *, user_id: int) -> list[ConsultSessionRow]:
        """本人会话列表，按更新时间倒序（FUNCTIONAL_SPEC 2.3）。`id` 作为
        稳定次级键，保证同一时间戳下顺序可复现。"""
        rows = (
            (
                await self._session.execute(
                    select(ConsultSessionRow)
                    .where(ConsultSessionRow.user_id == user_id)
                    .order_by(
                        ConsultSessionRow.update_time.desc(),
                        ConsultSessionRow.id.desc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        return list(rows)

    async def find_session_by_id(self, session_id: int) -> ConsultSessionRow | None:
        """按会话号取会话，**不校验归属**（FUNCTIONAL_SPEC 5.7「消息查询过滤」）。"""
        return await self._session.get(ConsultSessionRow, session_id)

    async def messages(self, session_id: int) -> list[ConsultMessageRow]:
        """会话全部消息，按写入顺序（`id` 升序）。"""
        rows = (
            (
                await self._session.execute(
                    select(ConsultMessageRow)
                    .where(ConsultMessageRow.session_id == session_id)
                    .order_by(ConsultMessageRow.id.asc())
                )
            )
            .scalars()
            .all()
        )
        return list(rows)

    async def add_message(
        self,
        session_id: int,
        *,
        role: str,
        content: str,
        references_json: str | None = None,
        graph_json: str | None = None,
        cost_time: int | None = None,
    ) -> ConsultMessageRow:
        row = ConsultMessageRow(
            session_id=session_id,
            role=role,
            content=content,
            references_json=references_json,
            graph_json=graph_json,
            cost_time=cost_time,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def history(
        self, session_id: int, *, exclude_message_id: int, limit: int
    ) -> list[ConsultMessageRow]:
        """本会话全部消息排除最后一条（刚保存的用户消息），取最近 `limit` 条，按时间升序。"""
        rows = (
            (
                await self._session.execute(
                    select(ConsultMessageRow)
                    .where(
                        ConsultMessageRow.session_id == session_id,
                        ConsultMessageRow.id != exclude_message_id,
                    )
                    .order_by(ConsultMessageRow.id.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return list(reversed(rows))

    async def complete_turn(
        self,
        session_id: int,
        *,
        assistant_content: str,
        references_json: str | None,
        graph_json: str | None,
        cost_time: int | None,
    ) -> ConsultMessageRow:
        """助手消息在流完全结束后写入，并把会话消息数 +2（FUNCTIONAL_SPEC 5.7）。"""
        session_row = await self._session.get(ConsultSessionRow, session_id)
        if session_row is None:
            raise LookupError(f"会话不存在：{session_id}")
        session_row.message_count = (session_row.message_count or 0) + 2
        return await self.add_message(
            session_id,
            role=ASSISTANT_ROLE,
            content=assistant_content,
            references_json=references_json,
            graph_json=graph_json,
            cost_time=cost_time,
        )
