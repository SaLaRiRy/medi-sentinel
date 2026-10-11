"""health record source / consult link / withdraw (TICKET-AC-06)

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-11

闭环第二段：医生回复工单后可以把结论沉淀成档案。为此给 `t_health_record` 加三列：

- `source`：内容来源（`ai` / `doctor` / `patient`），默认 `doctor`。`ai` 只可能由
  医生的**显式确认**动作写入（`POST /records/doctor/from-consult`），
  不存在「AI 文本直接落病历」的路径。
- `consult_id`：来自哪张工单（可空，历史档案为 NULL）。
- `withdrawn`：0/1 软删（`FUNCTIONAL_SPEC.md` 5.11 的硬删会丢掉审计痕迹，
  这里刻意保留行，只把它从列表里摘掉）。

见 `models/health_record.py`（ADR-0001）。
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "t_health_record",
        sa.Column(
            "source", sa.String(10), nullable=False, server_default="doctor"
        ),
    )
    op.add_column(
        "t_health_record", sa.Column("consult_id", sa.Integer, nullable=True)
    )
    op.add_column(
        "t_health_record",
        sa.Column("withdrawn", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_t_health_record_source", "t_health_record", ["source"])
    op.create_index("ix_t_health_record_consult_id", "t_health_record", ["consult_id"])


def downgrade() -> None:
    op.drop_index("ix_t_health_record_consult_id", table_name="t_health_record")
    op.drop_index("ix_t_health_record_source", table_name="t_health_record")
    op.drop_column("t_health_record", "withdrawn")
    op.drop_column("t_health_record", "consult_id")
    op.drop_column("t_health_record", "source")
