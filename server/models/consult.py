"""AI 问诊会话与消息（TICKET-007，字段语义见 `FUNCTIONAL_SPEC.md` 4.3.7 / 4.3.8）。

`user_id` 目前可空：账号表由 TICKET-012 建立，身份在那一票才接入，因此本票先落
一条无归属的会话，不伪造用户。TICKET-012 补上 `t_user` 后收紧为 `NOT NULL` + 外键。
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base

TITLE_MAX_LENGTH = 200
DEFAULT_TITLE = "新会话"


def _now() -> datetime:
    return datetime.now(UTC)


class ConsultSessionRow(Base):
    __tablename__ = "t_consult_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(TITLE_MAX_LENGTH), default=DEFAULT_TITLE)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=_now)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class ConsultMessageRow(Base):
    __tablename__ = "t_consult_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("t_consult_session.id"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    references_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    graph_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_time: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=_now)
