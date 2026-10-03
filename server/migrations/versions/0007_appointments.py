"""appointments (TICKET-017)

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-03

预约挂号表（FUNCTIONAL_SPEC 4.3.5）：患者选医生、科室、就诊日期与时段提交，
默认状态 0「待确认」。`department_id` 是裸整数，科室主数据由 TICKET-020 建立，
与 `t_doctor.department_id` 的现状一致；`user_id` / `doctor_id` 只建索引不建
外键，沿用 `models/consult.py` 对账号类引用的做法。见 `models/appointment.py`
的对应定义（ADR-0001）。
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "t_appointment",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("doctor_id", sa.Integer, nullable=False),
        sa.Column("department_id", sa.Integer, nullable=False),
        sa.Column("visit_date", sa.Date, nullable=False),
        sa.Column("time_slot", sa.String(20), nullable=False),
        sa.Column("status", sa.Integer, nullable=False, server_default="0"),
        sa.Column("remark", sa.String(255), nullable=True),
        sa.Column("create_time", sa.DateTime, nullable=True),
        sa.Column("update_time", sa.DateTime, nullable=True),
    )
    op.create_index("ix_t_appointment_user_id", "t_appointment", ["user_id"])
    op.create_index("ix_t_appointment_doctor_id", "t_appointment", ["doctor_id"])


def downgrade() -> None:
    op.drop_index("ix_t_appointment_doctor_id", table_name="t_appointment")
    op.drop_index("ix_t_appointment_user_id", table_name="t_appointment")
    op.drop_table("t_appointment")
