"""structured trace span detail (TICKET-011)

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-03

003 挂账第 1 条: the 200-character `output_digest` truncates a span's audit facts
when a message trips several red flags or a query returns several references, so
the later entries' hit id / matched fragment / rule version were lost. `detail`
stores those facts in structured form (JSON), unbounded by the digest limit but
still free of raw patient text and full model output (SPEC.md 3.7). See
`models/trace.py` for the matching definition (ADR-0001).
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trace_span", sa.Column("detail", sa.JSON, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("trace_span") as batch:
        batch.drop_column("detail")
