"""baseline: open the migration chain before the first domain table

Revision ID: 0001
Revises:
Create Date: 2026-10-03

This revision intentionally creates no tables. The skeleton owns no domain
entities; the first domain table arrives with TICKET-012. What it establishes
is the chain itself, so every later change is an auditable migration (ADR-0001).
"""

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No domain tables yet; the schema is the empty database plus the version stamp."""


def downgrade() -> None:
    """Nothing to undo."""
