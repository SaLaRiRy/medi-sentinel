"""consult session link (TICKET-AC-05)

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-11

把人工问诊工单与 AI 会话关联起来：`t_doctor_consult.session_id` 可空 + 索引。
历史工单为 NULL（新建这一列时还没有关联能力），医生端因此在没有会话时返回空上下文，
而不是报错。列可空是刻意的：患者转人工时可以不带会话（`SPEC.md` 5.3 的
`ConsultCreateRequest.session_id` 也是可选）。见 `models/doctor_consult.py`（ADR-0001）。
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "t_doctor_consult",
        sa.Column("session_id", sa.Integer, nullable=True),
    )
    op.create_index(
        "ix_t_doctor_consult_session_id", "t_doctor_consult", ["session_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_t_doctor_consult_session_id", table_name="t_doctor_consult")
    op.drop_column("t_doctor_consult", "session_id")
