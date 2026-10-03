"""B-5: 预约挂号的异步存取（TICKET-017）。

会话拥有交易边界：这里不提交，由 `core.deps.get_session` 决定记录的可见性。
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import Select, func, or_, select

from models.accounts import DoctorRow, UserRow
from models.appointment import AppointmentRow
from repositories.base import Repository


@dataclass(frozen=True)
class AppointmentRecord:
    """一条预约加上两侧的展示名（供 `AppointmentView` 组装，不落库）。"""

    row: AppointmentRow
    patient_name: str | None
    doctor_name: str | None


def _records(result) -> list[AppointmentRecord]:
    return [
        AppointmentRecord(
            row=row, patient_name=patient_name, doctor_name=doctor_name
        )
        for row, patient_name, doctor_name in result.all()
    ]


class AppointmentRepository(Repository):
    def _detail_query(self) -> Select:
        """预约行加上患者名与医生名；账号缺失时名称为 `None`，行仍可读。"""
        return (
            select(
                AppointmentRow,
                func.coalesce(UserRow.real_name, UserRow.username).label(
                    "patient_name"
                ),
                DoctorRow.real_name.label("doctor_name"),
            )
            .outerjoin(UserRow, UserRow.id == AppointmentRow.user_id)
            .outerjoin(DoctorRow, DoctorRow.id == AppointmentRow.doctor_id)
        )

    async def create(
        self,
        *,
        user_id: int,
        doctor_id: int,
        department_id: int,
        visit_date: date,
        time_slot: str,
        remark: str | None = None,
    ) -> AppointmentRow:
        """落库一条预约，状态取默认 0「待确认」（FUNCTIONAL_SPEC.md 4.3.5）。"""
        row = AppointmentRow(
            user_id=user_id,
            doctor_id=doctor_id,
            department_id=department_id,
            visit_date=visit_date,
            time_slot=time_slot,
            remark=remark,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_for_user(self, user_id: int) -> list[AppointmentRecord]:
        """患者本人的预约，新提交的在前（`GET /appointments/my`）。"""
        result = await self._session.execute(
            self._detail_query()
            .where(AppointmentRow.user_id == user_id)
            .order_by(AppointmentRow.id.desc())
        )
        return _records(result)

    async def list_for_doctor(self, doctor_id: int) -> list[AppointmentRecord]:
        """医生本人的排期，按就诊日期升序（`GET /appointments/doctor`）。"""
        result = await self._session.execute(
            self._detail_query()
            .where(AppointmentRow.doctor_id == doctor_id)
            .order_by(AppointmentRow.visit_date.asc(), AppointmentRow.id.asc())
        )
        return _records(result)

    def _criteria(
        self,
        *,
        keyword: str | None,
        department_id: int | None,
        visit_date: date | None,
        status: int | None,
    ) -> list:
        criteria = []
        if department_id is not None:
            criteria.append(AppointmentRow.department_id == department_id)
        if visit_date is not None:
            criteria.append(AppointmentRow.visit_date == visit_date)
        if status is not None:
            criteria.append(AppointmentRow.status == status)
        if keyword:
            pattern = f"%{keyword}%"
            criteria.append(
                or_(
                    UserRow.real_name.like(pattern),
                    UserRow.username.like(pattern),
                    DoctorRow.real_name.like(pattern),
                    AppointmentRow.remark.like(pattern),
                )
            )
        return criteria

    async def list_page(
        self,
        *,
        offset: int,
        limit: int,
        keyword: str | None = None,
        department_id: int | None = None,
        visit_date: date | None = None,
        status: int | None = None,
    ) -> tuple[list[AppointmentRecord], int]:
        """管理员分页列表，可按科室、就诊日期、状态与关键字过滤（SPEC.md 5.4）。"""
        criteria = self._criteria(
            keyword=keyword,
            department_id=department_id,
            visit_date=visit_date,
            status=status,
        )
        total = int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(AppointmentRow)
                    .outerjoin(UserRow, UserRow.id == AppointmentRow.user_id)
                    .outerjoin(DoctorRow, DoctorRow.id == AppointmentRow.doctor_id)
                    .where(*criteria)
                )
            ).scalar_one()
        )
        result = await self._session.execute(
            self._detail_query()
            .where(*criteria)
            .order_by(AppointmentRow.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return _records(result), total

    async def update_status(self, appointment_id: int, status: int) -> bool:
        """直接写入请求给定的状态值；记录不存在返回 `False`（→ 404）。"""
        row = await self._session.get(AppointmentRow, appointment_id)
        if row is None:
            return False
        row.status = status
        return True

    async def delete(self, appointment_id: int) -> bool:
        """删除预约；记录不存在返回 `False`（→ 404）。"""
        row = await self._session.get(AppointmentRow, appointment_id)
        if row is None:
            return False
        await self._session.delete(row)
        return True
