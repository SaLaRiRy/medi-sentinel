"""articles and notices (TICKET-021)

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-04

健康科普文章与系统公告（FUNCTIONAL_SPEC 4.3.11/4.3.12）：两者相互独立、与任何
其他实体无关联；`status` 缺省 1（已发布），文章 `view_count` 缺省 0。标题没有
数据库唯一约束。见 `models/article.py`（ADR-0001）。
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "t_article",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("cover", sa.String(255), nullable=True),
        sa.Column("summary", sa.String(500), nullable=True),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("view_count", sa.Integer, nullable=True, server_default="0"),
        sa.Column("status", sa.Integer, nullable=False, server_default="1"),
        sa.Column("create_time", sa.DateTime, nullable=True),
        sa.Column("update_time", sa.DateTime, nullable=True),
    )
    op.create_table(
        "t_notice",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("status", sa.Integer, nullable=False, server_default="1"),
        sa.Column("create_time", sa.DateTime, nullable=True),
        sa.Column("update_time", sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("t_notice")
    op.drop_table("t_article")
