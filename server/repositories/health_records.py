"""B-5: 健康档案的异步存取（TICKET-018）。

会话拥有交易边界：这里不提交，由 `core.deps.get_session` 决定记录的可见性。
更新与删除同时以「档案号 **且** 医生号」为过滤条件，从 SQL 层就把他人名下的
档案挡在外面 —— 不匹配即 `None`/`False`，对外是 404（`FUNCTIONAL_SPEC.md` 5.16）。
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import Select, func, select, union

from models.accounts import DoctorRow, UserRow
from models.appointment import AppointmentRow
from models.doctor_consult import DoctorConsultRow
from models.health_record import HealthRecordRow
from repositories.base import Repository


@dataclass(frozen=True)
class HealthRecordRecord:
    """一条档案加上患者名与医生名（供 `HealthRecordView` 组装，不落库）。"""

    row: HealthRecordRow
    patient_name: str | None
    doctor_name: str | None


@dataclass(frozen=True)
class PatientOption:
    """建档时可选的病人（`FUNCTIONAL_SPEC.md` 5.16）。"""

    id: int
    name: str


def _records(result) -> list[HealthRecordRecord]:
    return [
        HealthRecordRecord(
            row=row, patient_name=patient_name, doctor_name=doctor_name
        )
        for row, patient_name, doctor_name in result.all()
    ]


class HealthRecordRepository(Repository):
    def _detail_query(self) -> Select:
        """档案行加上患者名与医生名；账号缺失时名称为 `None`，行仍可读。"""
        return (
            select(
                HealthRecordRow,
                func.coalesce(UserRow.real_name, UserRow.username).label(
                    "patient_name"
                ),
                DoctorRow.real_name.label("doctor_name"),
            )
            .outerjoin(UserRow, UserRow.id == HealthRecordRow.user_id)
            .outerjoin(DoctorRow, DoctorRow.id == HealthRecordRow.doctor_id)
        )

    async def _detail(self, record_id: int) -> HealthRecordRecord | None:
        result = await self._session.execute(
            self._detail_query().where(HealthRecordRow.id == record_id)
        )
        records = _records(result)
        return records[0] if records else None

    async def create(
        self,
        *,
        doctor_id: int,
        user_id: int,
        record_type: str,
        diagnosis: str | None = None,
        treatment: str | None = None,
        prescription: str | None = None,
        visit_date: date | None = None,
    ) -> HealthRecordRecord | None:
        """为患者建档；患者不存在返回 `None`（→ 404，SPEC.md 5.4「POST 404」）。"""
        if await self._session.get(UserRow, user_id) is None:
            return None
        row = HealthRecordRow(
            user_id=user_id,
            doctor_id=doctor_id,
            record_type=record_type,
            diagnosis=diagnosis,
            treatment=treatment,
            prescription=prescription,
            visit_date=visit_date,
        )
        self._session.add(row)
        await self._session.flush()
        return await self._detail(row.id)

    async def list_for_user(self, user_id: int) -> list[HealthRecordRecord]:
        """患者本人的档案，新建立的在前（`GET /records/my`）。"""
        result = await self._session.execute(
            self._detail_query()
            .where(HealthRecordRow.user_id == user_id)
            .order_by(HealthRecordRow.id.desc())
        )
        return _records(result)

    async def list_for_doctor(self, doctor_id: int) -> list[HealthRecordRecord]:
        """医生名下的档案，新建立的在前（`GET /records/doctor`）。"""
        result = await self._session.execute(
            self._detail_query()
            .where(HealthRecordRow.doctor_id == doctor_id)
            .order_by(HealthRecordRow.id.desc())
        )
        return _records(result)

    async def patient_options(self, doctor_id: int) -> list[PatientOption]:
        """可选患者 = 该医生的预约人 ∪ 问诊人 ∪ 已建档人，去重（FUNCTIONAL_SPEC 5.16）。

        「问诊人」一支由 TICKET-019 承接（TICKET-018 挂账第 1 条）：工单的
        `doctor_id` 为当前医生时，提交人计入；「待分配」工单不属于任何医生。"""
        appointment_ids = (
            select(AppointmentRow.user_id)
            .where(AppointmentRow.doctor_id == doctor_id)
            .distinct()
        )
        record_ids = (
            select(HealthRecordRow.user_id)
            .where(HealthRecordRow.doctor_id == doctor_id)
            .distinct()
        )
        consult_ids = (
            select(DoctorConsultRow.user_id)
            .where(DoctorConsultRow.doctor_id == doctor_id)
            .distinct()
        )
        statement = (
            select(
                UserRow.id,
                func.coalesce(UserRow.real_name, UserRow.username),
            )
            .where(UserRow.id.in_(union(appointment_ids, record_ids, consult_ids)))
            .order_by(UserRow.id)
        )
        rows = (await self._session.execute(statement)).all()
        return [PatientOption(id=row[0], name=row[1]) for row in rows]

    async def update(
        self, record_id: int, doctor_id: int, fields: dict
    ) -> HealthRecordRecord | None:
        """更新本医生名下的档案；不匹配（不存在或他人名下）返回 `None`（→ 404）。"""
        row = (
            await self._session.execute(
                select(HealthRecordRow).where(
                    HealthRecordRow.id == record_id,
                    HealthRecordRow.doctor_id == doctor_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        for key, value in fields.items():
            setattr(row, key, value)
        await self._session.flush()
        return await self._detail(record_id)

    async def delete(self, record_id: int, doctor_id: int) -> bool:
        """删除本医生名下的档案；不匹配返回 `False`（→ 404）。"""
        row = (
            await self._session.execute(
                select(HealthRecordRow).where(
                    HealthRecordRow.id == record_id,
                    HealthRecordRow.doctor_id == doctor_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return False
        await self._session.delete(row)
        return True
