"""人工问诊工单与医生回复（TICKET-019，字段语义见 `FUNCTIONAL_SPEC.md` 4.3.9 / 4.3.10）。

患者提交工单时可指定医生，也可留空成为「待分配」——`doctor_id` 为空时工单对
所有医生可见，由首位回复的医生认领（`FUNCTIONAL_SPEC.md` 5.14）。`user_id` /
`doctor_id` 只建索引不建外键，沿用 `models/appointment.py` 对账号类引用的做法；
`t_doctor_reply.consult_id` 相反，它是同一业务域内的子记录，建真正的外键以便
级联删除按「先回复后工单」的顺序执行（`FUNCTIONAL_SPEC.md` 5.11）。

`session_id`（TICKET-AC-05）把工单指回 AI 会话：患者转人工时带上会话，医生就能在
工单里看到 AI 已经问出来的候选疾病与引用，不必让患者重打一遍主诉。可空——历史工单
与「不带会话转人工」都落在 NULL 上，此时医生端返回空上下文而不是报错。
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base

# 工单状态（FUNCTIONAL_SPEC.md 5.10）：0 待回复（默认）/ 1 已回复。
CONSULT_STATUS_PENDING = 0
CONSULT_STATUS_REPLIED = 1


def _now() -> datetime:
    return datetime.now(UTC)


class DoctorConsultRow(Base):
    __tablename__ = "t_doctor_consult"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    doctor_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    #: 关联的 AI 会话号（TICKET-AC-05）；NULL = 未关联/历史工单。
    session_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    chief_complaint: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[int] = mapped_column(
        Integer, default=CONSULT_STATUS_PENDING, nullable=False
    )
    create_time: Mapped[datetime] = mapped_column(DateTime, default=_now)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class DoctorReplyRow(Base):
    __tablename__ = "t_doctor_reply"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    consult_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("t_doctor_consult.id"), nullable=False, index=True
    )
    doctor_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=_now)
