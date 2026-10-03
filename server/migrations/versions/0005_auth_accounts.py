"""three-role account tables (TICKET-012)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-03

The token layer needs one table per role (FUNCTIONAL_SPEC 4.3.1-4.3.3): a login
carries `role`, which picks the table to read, so the same username may live in
all three. `username` is unique within each table, not across them. See
`models/accounts.py` for the matching definitions (ADR-0001).
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _shared_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("password", sa.String(100), nullable=False),
        sa.Column("avatar", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("status", sa.Integer, nullable=False, server_default="1"),
        sa.Column("create_time", sa.DateTime, nullable=False),
        sa.Column("update_time", sa.DateTime, nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "t_user",
        *_shared_columns(),
        sa.Column("real_name", sa.String(50), nullable=True),
        sa.Column("gender", sa.Integer, nullable=False, server_default="1"),
        sa.Column("age", sa.Integer, nullable=True),
        sa.Column("allergy_history", sa.Text, nullable=True),
    )

    op.create_table(
        "t_doctor",
        *_shared_columns(),
        sa.Column("real_name", sa.String(50), nullable=False),
        sa.Column("department_id", sa.Integer, nullable=True),
        sa.Column("title", sa.String(50), nullable=True),
        sa.Column("specialty", sa.String(255), nullable=True),
        sa.Column("introduction", sa.Text, nullable=True),
    )

    op.create_table(
        "t_admin",
        *_shared_columns(),
        sa.Column("nickname", sa.String(50), nullable=True),
        sa.Column("email", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("t_admin")
    op.drop_table("t_doctor")
    op.drop_table("t_user")
