"""科室主数据（TICKET-020，字段语义见 `FUNCTIONAL_SPEC.md` 4.3.4）。

`name` 在数据库层没有唯一约束，唯一性由应用层保证（`FUNCTIONAL_SPEC.md` 4.5）；
`sort_order` 缺省 0，公开列表按它升序、同值按编号倒序（`FUNCTIONAL_SPEC.md` 5.13）。
医生与预约引用的是本科室的编号，`models/accounts.py` / `models/appointment.py`
沿用「账号类引用只建索引不建外键」的做法，删除保护与级联由业务层负责。
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base

DEPARTMENT_NAME_MAX_LENGTH = 50
DEPARTMENT_DESCRIPTION_MAX_LENGTH = 255


def _now() -> datetime:
    return datetime.now(UTC)


class DepartmentRow(Base):
    __tablename__ = "t_department"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(DEPARTMENT_NAME_MAX_LENGTH), nullable=False
    )
    description: Mapped[str | None] = mapped_column(
        String(DEPARTMENT_DESCRIPTION_MAX_LENGTH), nullable=True
    )
    sort_order: Mapped[int | None] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(Integer, default=1)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=_now)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
