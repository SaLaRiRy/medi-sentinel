"""doctor consults (TICKET-019)

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-04

人工问诊工单与医生回复（FUNCTIONAL_SPEC 4.3.9 / 4.3.10）：患者提交工单，
医生认领并回复。`t_doctor_consult.doctor_id` 可空表示「待分配」；`status`
默认 0「待回复」，医生回复时置 1。`t_doctor_reply.consult_id` 建真正的外键，
级联删除按「先回复后工单」顺序执行。见 `models/doctor_consult.py`（ADR-0001）。
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "t_doctor_consult",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("doctor_id", sa.Integer, nullable=True),
        sa.Column("chief_complaint", sa.Text, nullable=False),
        sa.Column("status", sa.Integer, nullable=False, server_default="0"),
        sa.Column("create_time", sa.DateTime, nullable=True),
        sa.Column("update_time", sa.DateTime, nullable=True),
    )
    op.create_index("ix_t_doctor_consult_user_id", "t_doctor_consult", ["user_id"])
    op.create_index("ix_t_doctor_consult_doctor_id", "t_doctor_consult", ["doctor_id"])

    op.create_table(
        "t_doctor_reply",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "consult_id",
            sa.Integer,
            sa.ForeignKey("t_doctor_consult.id"),
            nullable=False,
        ),
        sa.Column("doctor_id", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("create_time", sa.DateTime, nullable=True),
    )
    op.create_index("ix_t_doctor_reply_consult_id", "t_doctor_reply", ["consult_id"])
    op.create_index("ix_t_doctor_reply_doctor_id", "t_doctor_reply", ["doctor_id"])


def downgrade() -> None:
    op.drop_index("ix_t_doctor_reply_doctor_id", table_name="t_doctor_reply")
    op.drop_index("ix_t_doctor_reply_consult_id", table_name="t_doctor_reply")
    op.drop_table("t_doctor_reply")
    op.drop_index("ix_t_doctor_consult_doctor_id", table_name="t_doctor_consult")
    op.drop_index("ix_t_doctor_consult_user_id", table_name="t_doctor_consult")
    op.drop_table("t_doctor_consult")
