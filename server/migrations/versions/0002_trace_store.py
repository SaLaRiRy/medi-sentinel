"""trace store: spans and route decisions (TICKET-002)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-03

The first tables are not domain entities — they are the trace foundation
(SPEC.md 4.1 B-4/B-5): one row per Skill/LLM span, one row per consult's route
decision. See `models/trace.py` for the matching definitions (ADR-0001).
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trace_span",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("trace_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("duration_ms", sa.Integer, nullable=False),
        sa.Column("input_digest", sa.String(200), nullable=False),
        sa.Column("output_digest", sa.String(200), nullable=False),
        sa.Column("started_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_trace_span_trace_id", "trace_span", ["trace_id"])
    op.create_index("ix_trace_span_started_at", "trace_span", ["started_at"])

    op.create_table(
        "route_decision",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("trace_id", sa.String(64), nullable=False),
        sa.Column("skills_run", sa.JSON, nullable=False),
        sa.Column("skills_skipped", sa.JSON, nullable=False),
        sa.Column("decided_at", sa.DateTime, nullable=False),
    )
    op.create_index(
        "ix_route_decision_trace_id", "route_decision", ["trace_id"], unique=True
    )
    op.create_index("ix_route_decision_decided_at", "route_decision", ["decided_at"])


def downgrade() -> None:
    op.drop_index("ix_route_decision_decided_at", table_name="route_decision")
    op.drop_index("ix_route_decision_trace_id", table_name="route_decision")
    op.drop_table("route_decision")
    op.drop_index("ix_trace_span_started_at", table_name="trace_span")
    op.drop_index("ix_trace_span_trace_id", table_name="trace_span")
    op.drop_table("trace_span")
