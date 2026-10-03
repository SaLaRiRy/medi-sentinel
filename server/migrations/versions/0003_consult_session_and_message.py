"""consult sessions and messages (TICKET-007)

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-03

The first domain tables: `POST /chat/send` needs somewhere to keep the session
title, the message count and the history the prompt assembles (FUNCTIONAL_SPEC
4.3.7 / 4.3.8, 5.7). `user_id` stays nullable here because the account tables
arrive with TICKET-012, which tightens the column to a real foreign key.
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "t_consult_session",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=True),
        sa.Column("title", sa.String(200), nullable=True, server_default="新会话"),
        sa.Column("message_count", sa.Integer, nullable=True, server_default="0"),
        sa.Column("create_time", sa.DateTime, nullable=True),
        sa.Column("update_time", sa.DateTime, nullable=True),
    )
    op.create_index("ix_t_consult_session_user_id", "t_consult_session", ["user_id"])

    op.create_table(
        "t_consult_message",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Integer,
            sa.ForeignKey("t_consult_session.id"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("references_json", sa.Text, nullable=True),
        sa.Column("graph_json", sa.Text, nullable=True),
        sa.Column("cost_time", sa.Integer, nullable=True, server_default="0"),
        sa.Column("create_time", sa.DateTime, nullable=True),
    )
    op.create_index(
        "ix_t_consult_message_session_id", "t_consult_message", ["session_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_t_consult_message_session_id", table_name="t_consult_message")
    op.drop_table("t_consult_message")
    op.drop_index("ix_t_consult_session_user_id", table_name="t_consult_session")
    op.drop_table("t_consult_session")
