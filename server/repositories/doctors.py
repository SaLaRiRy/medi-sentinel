"""B-5: 医生目录的只读投影（TICKET-020，`SPEC.md` 5.4「患者与医生主数据」）。

医生的增删改走 `AccountRepository`（账号行的通用操作）；本模块只负责列表查询，
因为它们需要把 `t_doctor.department_id` 拼上科室名，并且公开列表与管理员列表
的可见范围不同：公开列表只显示状态为 1 且已分配科室的医生（FUNCTIONAL_SPEC 2.5）。
"""

from dataclasses import dataclass

from sqlalchemy import Select, func, or_, select

from models.accounts import DoctorRow
from models.department import DepartmentRow
from repositories.base import Repository


@dataclass(frozen=True)
class DoctorRecord:
    """一位医生加上科室名（供 `DoctorView` 组装，不落库）。"""

    row: DoctorRow
    department_name: str | None


class DoctorDirectoryRepository(Repository):
    def _query(self) -> Select:
        return (
            select(DoctorRow, DepartmentRow.name.label("department_name"))
            .outerjoin(DepartmentRow, DepartmentRow.id == DoctorRow.department_id)
            .order_by(DoctorRow.id.desc())
        )

    @staticmethod
    def _records(result) -> list[DoctorRecord]:
        return [
            DoctorRecord(row=row, department_name=department_name)
            for row, department_name in result.all()
        ]

    async def find_by_id(self, doctor_id: int) -> DoctorRecord | None:
        result = await self._session.execute(
            self._query().where(DoctorRow.id == doctor_id)
        )
        records = self._records(result)
        return records[0] if records else None

    async def list_public(
        self,
        *,
        offset: int,
        limit: int,
        department_id: int | None = None,
        keyword: str | None = None,
    ) -> tuple[list[DoctorRecord], int]:
        """公开列表：状态为 1 且已分配科室（FUNCTIONAL_SPEC 2.5 / 4.3.3）。"""
        criteria = [DoctorRow.status == 1, DoctorRow.department_id.is_not(None)]
        if department_id is not None:
            criteria.append(DoctorRow.department_id == department_id)
        if keyword:
            pattern = f"%{keyword}%"
            criteria.append(
                or_(DoctorRow.username.like(pattern), DoctorRow.real_name.like(pattern))
            )
        total = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(DoctorRow).where(*criteria)
                )
            ).scalar_one()
        )
        result = await self._session.execute(
            self._query().where(*criteria).offset(offset).limit(limit)
        )
        return self._records(result), total

    async def list_page(
        self, *, offset: int, limit: int, keyword: str | None = None
    ) -> tuple[list[DoctorRecord], int]:
        """管理员列表：全部状态，可选按登录名/真名检索（SPEC.md 5.4）。"""
        criteria = []
        if keyword:
            pattern = f"%{keyword}%"
            criteria.append(
                or_(DoctorRow.username.like(pattern), DoctorRow.real_name.like(pattern))
            )
        total = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(DoctorRow).where(*criteria)
                )
            ).scalar_one()
        )
        result = await self._session.execute(
            self._query().where(*criteria).offset(offset).limit(limit)
        )
        return self._records(result), total
