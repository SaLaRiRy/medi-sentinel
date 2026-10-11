"""健康档案（TICKET-018，字段语义见 `FUNCTIONAL_SPEC.md` 4.3.6）。

医生为患者建立的就诊记录：档案类型、诊断、治疗方案与处方。`user_id` 是归属患者，
`doctor_id` 可空（空表示该档案未归属到具体医生）。与 `models/appointment.py` 一致，
账号类引用只建索引不建外键，级联删除由业务层负责（`FUNCTIONAL_SPEC.md` 6.2/6.3）。

`record_type` 在库里可空（沿用 `FUNCTIONAL_SPEC.md` 4.3.6），但对外建档请求由
`SPEC.md` 5.3 的 `HealthRecordCreateRequest` 强制必填 1..50，缺省或越界由 422 拒绝。

TICKET-AC-06 加了三列：`source`（内容来源）、`consult_id`（来自哪张工单）、
`withdrawn`（0/1 软删）。**AI 文本不得直接落病历**——`source='ai'` 只能由
`POST /records/doctor/from-consult` 这个医生确认动作写入；撤回走软删，
保留行以便审计（硬删会连审计痕迹一起丢掉）。
"""

from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base

RECORD_TYPE_MAX_LENGTH = 50
DIAGNOSIS_MAX_LENGTH = 255

#: 内容来源。`ai` 只由医生的显式确认动作写入；`patient` 预留给患者自述（本票未接线）。
RECORD_SOURCES = ("ai", "doctor", "patient")
SOURCE_DOCTOR = "doctor"
SOURCE_MAX_LENGTH = 10


def _now() -> datetime:
    return datetime.now(UTC)


class HealthRecordRow(Base):
    __tablename__ = "t_health_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    doctor_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    #: 内容来源（`ai` / `doctor` / `patient`，TICKET-AC-06）。
    source: Mapped[str] = mapped_column(
        String(SOURCE_MAX_LENGTH), default=SOURCE_DOCTOR, nullable=False
    )
    #: 来自哪张人工问诊工单（TICKET-AC-06）；NULL = 非工单沉淀。
    consult_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    #: 0 正常 / 1 已撤回（软删，TICKET-AC-06）。
    withdrawn: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    record_type: Mapped[str | None] = mapped_column(
        String(RECORD_TYPE_MAX_LENGTH), nullable=True
    )
    diagnosis: Mapped[str | None] = mapped_column(
        String(DIAGNOSIS_MAX_LENGTH), nullable=True
    )
    treatment: Mapped[str | None] = mapped_column(Text, nullable=True)
    prescription: Mapped[str | None] = mapped_column(Text, nullable=True)
    visit_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, default=_now)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
