"""departments (TICKET-020)

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-04

科室主数据（FUNCTIONAL_SPEC 4.3.4）：`name` 无数据库唯一约束，唯一性由应用层
保证；`sort_order` 缺省 0，`status` 缺省 1。见 `models/department.py`（ADR-0001）。
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "t_department",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=True, server_default="0"),
        sa.Column("status", sa.Integer, nullable=False, server_default="1"),
        sa.Column("create_time", sa.DateTime, nullable=True),
        sa.Column("update_time", sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("t_department")
