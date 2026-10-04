"""health records (TICKET-018)

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-04

健康档案表（FUNCTIONAL_SPEC 4.3.6）：医生为患者建立的就诊记录，含档案类型、
诊断、治疗方案与处方。`user_id`（患者）与 `doctor_id` 只建索引不建外键，沿用
`t_appointment` 对账号类引用的做法；`doctor_id` 可空表示未归属到具体医生。
见 `models/health_record.py` 的对应定义（ADR-0001）。
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "t_health_record",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("doctor_id", sa.Integer, nullable=True),
        sa.Column("record_type", sa.String(50), nullable=True),
        sa.Column("diagnosis", sa.String(255), nullable=True),
        sa.Column("treatment", sa.Text, nullable=True),
        sa.Column("prescription", sa.Text, nullable=True),
        sa.Column("visit_date", sa.Date, nullable=True),
        sa.Column("create_time", sa.DateTime, nullable=True),
        sa.Column("update_time", sa.DateTime, nullable=True),
    )
    op.create_index("ix_t_health_record_user_id", "t_health_record", ["user_id"])
    op.create_index("ix_t_health_record_doctor_id", "t_health_record", ["doctor_id"])


def downgrade() -> None:
    op.drop_index("ix_t_health_record_doctor_id", table_name="t_health_record")
    op.drop_index("ix_t_health_record_user_id", table_name="t_health_record")
    op.drop_table("t_health_record")
