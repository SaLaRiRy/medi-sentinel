"""预约挂号（TICKET-017，字段语义见 `FUNCTIONAL_SPEC.md` 4.3.5）。

`department_id` 只是一枚整数编号：科室主数据（`t_department`）与它的删除保护
由 TICKET-020 建立，因此这里不声明外键，与 `models/accounts.py` 里
`DoctorRow.department_id` 的现状一致。同一患者可对同一医生、同一日期、同一
时段重复预约无限次 —— `FUNCTIONAL_SPEC.md` 4.3.5 明确不存在任何唯一性或号源
容量约束。
"""

from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base

# 预约状态（FUNCTIONAL_SPEC.md 5.10）：0 待确认（默认）/ 1 已确认 / 2 已完成 / 3 已取消。
APPOINTMENT_STATUS_PENDING = 0
APPOINTMENT_STATUS_CONFIRMED = 1
APPOINTMENT_STATUS_COMPLETED = 2
APPOINTMENT_STATUS_CANCELLED = 3

TIME_SLOT_MAX_LENGTH = 20
REMARK_MAX_LENGTH = 255


def _now() -> datetime:
    return datetime.now(UTC)


class AppointmentRow(Base):
    __tablename__ = "t_appointment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    doctor_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    department_id: Mapped[int] = mapped_column(Integer, nullable=False)
    visit_date: Mapped[date] = mapped_column(Date, nullable=False)
    time_slot: Mapped[str] = mapped_column(
        String(TIME_SLOT_MAX_LENGTH), nullable=False
    )
    status: Mapped[int] = mapped_column(
        Integer, default=APPOINTMENT_STATUS_PENDING, nullable=False
    )
    remark: Mapped[str | None] = mapped_column(
        String(REMARK_MAX_LENGTH), nullable=True
    )
    create_time: Mapped[datetime] = mapped_column(DateTime, default=_now)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
