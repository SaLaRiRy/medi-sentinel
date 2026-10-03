"""knowledge-base files and chunks (TICKET-013)

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-03

TICKET-006 挂账 landed with this ticket too: `server/docs_seed/` needs somewhere
to record each document and its chunks, and the seed/upload path needs a status
machine to move a file from 已上传 to 已向量化 (FUNCTIONAL_SPEC 4.3.13/4.3.14,
5.6). `file_name` is the business key the seed script de-dupes on; the vector id
`file_{id}_chunk_{index}` matches the index entry. See `models/knowledge.py`
for the matching definitions (ADR-0001).
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "t_knowledge_file",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(20), nullable=False),
        sa.Column("file_size", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("chunk_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("vector_status", sa.Integer, nullable=False, server_default="0"),
        sa.Column("upload_by", sa.Integer, nullable=True),
        sa.Column("upload_role", sa.String(20), nullable=True, server_default="admin"),
        sa.Column("create_time", sa.DateTime, nullable=True),
        sa.Column("update_time", sa.DateTime, nullable=True),
    )

    op.create_table(
        "t_knowledge_chunk",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "file_id",
            sa.Integer,
            sa.ForeignKey("t_knowledge_file.id"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("vector_id", sa.String(100), nullable=True),
        sa.Column("create_time", sa.DateTime, nullable=True),
    )
    op.create_index("ix_t_knowledge_chunk_file_id", "t_knowledge_chunk", ["file_id"])


def downgrade() -> None:
    op.drop_index("ix_t_knowledge_chunk_file_id", table_name="t_knowledge_chunk")
    op.drop_table("t_knowledge_chunk")
    op.drop_table("t_knowledge_file")
