"""B-5: 科室主数据的异步存取（TICKET-020）。

会话拥有交易边界：这里不提交，由 `core.deps.get_session` 决定记录的可见性。
`doctor_count` 的统计口径是「已分配科室且状态为 1 的医生」（`FUNCTIONAL_SPEC.md`
5.13）；删除保护则统计**全部**隶属于该科室的医生（5.12），两者刻意不同。
"""

from dataclasses import dataclass

from sqlalchemy import Select, func, select

from models.accounts import DoctorRow
from models.department import DepartmentRow
from repositories.base import Repository


@dataclass(frozen=True)
class DepartmentRecord:
    """一个科室加上它的在岗医生数（供 `DepartmentView` 组装，不落库）。"""

    row: DepartmentRow
    doctor_count: int


class DepartmentRepository(Repository):
    def _doctor_count(self):
        return (
            select(func.count())
            .select_from(DoctorRow)
            .where(
                DoctorRow.department_id == DepartmentRow.id,
                DoctorRow.status == 1,
            )
            .correlate(DepartmentRow)
            .scalar_subquery()
        )

    def _query(self) -> Select:
        return select(DepartmentRow, self._doctor_count().label("doctor_count"))

    def _ordered(self, query: Select) -> Select:
        """公开列表排序：`sort_order` 升序、同值按编号倒序（FUNCTIONAL_SPEC 5.13）。"""
        return query.order_by(
            func.coalesce(DepartmentRow.sort_order, 0).asc(),
            DepartmentRow.id.desc(),
        )

    @staticmethod
    def _records(result) -> list[DepartmentRecord]:
        return [
            DepartmentRecord(row=row, doctor_count=int(count))
            for row, count in result.all()
        ]

    async def list_public(self) -> list[DepartmentRecord]:
        """公开列表：只返回状态为 1 的科室（FUNCTIONAL_SPEC 5.13）。"""
        result = await self._session.execute(
            self._ordered(self._query().where(DepartmentRow.status == 1))
        )
        return self._records(result)

    async def list_page(
        self, *, offset: int, limit: int, keyword: str | None = None
    ) -> tuple[list[DepartmentRecord], int]:
        """管理员分页列表：全部状态，按需按名称检索（SPEC.md 5.4）。"""
        criteria = []
        if keyword:
            criteria.append(DepartmentRow.name.like(f"%{keyword}%"))
        total = int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(DepartmentRow)
                    .where(*criteria)
                )
            ).scalar_one()
        )
        result = await self._session.execute(
            self._ordered(self._query().where(*criteria))
            .offset(offset)
            .limit(limit)
        )
        return self._records(result), total

    async def find_by_id(self, department_id: int) -> DepartmentRecord | None:
        result = await self._session.execute(
            self._query().where(DepartmentRow.id == department_id)
        )
        records = self._records(result)
        return records[0] if records else None

    async def find_by_name(
        self, name: str, *, exclude_id: int | None = None
    ) -> DepartmentRow | None:
        """科室名唯一性在应用层保证（FUNCTIONAL_SPEC 4.5）；更新时排除自身。"""
        criteria = [DepartmentRow.name == name]
        if exclude_id is not None:
            criteria.append(DepartmentRow.id != exclude_id)
        return (
            await self._session.execute(select(DepartmentRow).where(*criteria))
        ).scalar_one_or_none()

    async def create(
        self, *, name: str, description: str | None, sort_order: int
    ) -> DepartmentRecord:
        row = DepartmentRow(
            name=name, description=description, sort_order=sort_order
        )
        self._session.add(row)
        await self._session.flush()
        return DepartmentRecord(row=row, doctor_count=0)

    async def update(self, department_id: int, fields: dict) -> DepartmentRecord | None:
        """按给定字段更新；记录不存在返回 `None`（→ 404）。"""
        row = await self._session.get(DepartmentRow, department_id)
        if row is None:
            return None
        for key, value in fields.items():
            setattr(row, key, value)
        await self._session.flush()
        return await self.find_by_id(department_id)

    async def count_assigned_doctors(self, department_id: int) -> int:
        """隶属于该科室的医生数，**不按状态过滤**（FUNCTIONAL_SPEC 5.12）。"""
        return int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(DoctorRow)
                    .where(DoctorRow.department_id == department_id)
                )
            ).scalar_one()
        )

    async def delete(self, department_id: int) -> tuple[bool, int]:
        """删除空科室；仍有关联医生时返回 `(True, N)` 交给路由转 409。"""
        row = await self._session.get(DepartmentRow, department_id)
        if row is None:
            return False, 0
        doctors = await self.count_assigned_doctors(department_id)
        if doctors:
            return True, doctors
        await self._session.delete(row)
        return True, 0
