"""三角色账号表（TICKET-012，字段语义见 `FUNCTIONAL_SPEC.md` 4.3.1-4.3.3）。

系统没有角色字段：同一用户名可在三张表并存，令牌里的 `role` 声明决定后续
每个请求查哪一张表（FUNCTIONAL_SPEC 2.2「角色模型」）。
"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base

USERNAME_MAX_LENGTH = 50
PASSWORD_MAX_LENGTH = 100


def _now() -> datetime:
    return datetime.now(UTC)


class AccountRowMixin:
    """The columns all three account tables share (FUNCTIONAL_SPEC 4.3.1-4.3.3)."""

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(
        String(USERNAME_MAX_LENGTH), nullable=False, unique=True
    )
    password: Mapped[str] = mapped_column(String(PASSWORD_MAX_LENGTH), nullable=False)
    avatar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[int] = mapped_column(Integer, default=1)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=_now)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class UserRow(AccountRowMixin, Base):
    """患者（`t_user`）。`real_name` 是昵称，`gender` 1 男 / 2 女。"""

    __tablename__ = "t_user"

    real_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    gender: Mapped[int] = mapped_column(Integer, default=1)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allergy_history: Mapped[str | None] = mapped_column(Text, nullable=True)


class DoctorRow(AccountRowMixin, Base):
    """医生（`t_doctor`）。`department_id` 可空：医生可以不属于任何科室。"""

    __tablename__ = "t_doctor"

    real_name: Mapped[str] = mapped_column(String(50), nullable=False)
    department_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(String(50), nullable=True)
    specialty: Mapped[str | None] = mapped_column(String(255), nullable=True)
    introduction: Mapped[str | None] = mapped_column(Text, nullable=True)


class AdminRow(AccountRowMixin, Base):
    """管理员（`t_admin`）。用 `nickname` 而不是 `real_name`，另有 `email`。"""

    __tablename__ = "t_admin"

    nickname: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
