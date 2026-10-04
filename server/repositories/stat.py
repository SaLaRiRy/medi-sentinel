"""B-5: 数据统计的异步聚合（TICKET-022）。

统计全部只读：六项总数、医生工作台、患者个人概览、最近 N 个自然日的问诊趋势与
用户增长、按科室的预约分布、按类型的知识库分布，都直接来自既有实体
（`FUNCTIONAL_SPEC.md` 2.9），不新增任何表。会话拥有事务边界，这里不提交。

「自然日」一律按 **UTC** 计算：模型的时间戳由 `datetime.now(UTC)` 生成
（`models/*.py`），SQLite 以朴素 UTC 墙钟存取（`repositories/trace.py`），
所以按存储值的日期分桶即可，不引入本地时区。窗口比较同样用朴素 UTC 边界。
"""

from datetime import date, datetime, time, timedelta

from sqlalchemy import func, or_, select, union

from models.accounts import DoctorRow, UserRow
from models.appointment import AppointmentRow
from models.article import ArticleRow
from models.consult import ConsultSessionRow
from models.department import DepartmentRow
from models.doctor_consult import (
    CONSULT_STATUS_PENDING,
    CONSULT_STATUS_REPLIED,
    DoctorConsultRow,
)
from models.health_record import HealthRecordRow
from models.knowledge import KnowledgeFileRow
from repositories.base import Repository


class StatRepository(Repository):
    async def _count(self, model, *criteria) -> int:
        return int(
            (
                await self._session.execute(
                    select(func.count()).select_from(model).where(*criteria)
                )
            ).scalar_one()
        )

    # --- 管理员概览：六项总数 -------------------------------------------------

    async def count_users(self) -> int:
        return await self._count(UserRow)

    async def count_doctors(self) -> int:
        return await self._count(DoctorRow)

    async def count_sessions(self) -> int:
        return await self._count(ConsultSessionRow)

    async def count_appointments(self) -> int:
        return await self._count(AppointmentRow)

    async def count_knowledge_files(self) -> int:
        return await self._count(KnowledgeFileRow)

    async def count_articles(self) -> int:
        return await self._count(ArticleRow)

    # --- 医生工作台 -----------------------------------------------------------

    async def count_pending_consults(self, doctor_id: int) -> int:
        """指派给我 **或** 尚未指派，且状态为 0（FUNCTIONAL_SPEC 2.9）。"""
        return await self._count(
            DoctorConsultRow,
            DoctorConsultRow.status == CONSULT_STATUS_PENDING,
            or_(
                DoctorConsultRow.doctor_id == doctor_id,
                DoctorConsultRow.doctor_id.is_(None),
            ),
        )

    async def count_appointments_on(self, doctor_id: int, day: date) -> int:
        """就诊日期为今天、且指给我的预约数（FUNCTIONAL_SPEC 2.9）。"""
        return await self._count(
            AppointmentRow,
            AppointmentRow.doctor_id == doctor_id,
            AppointmentRow.visit_date == day,
        )

    async def count_replied_consults(self, doctor_id: int) -> int:
        return await self._count(
            DoctorConsultRow,
            DoctorConsultRow.doctor_id == doctor_id,
            DoctorConsultRow.status == CONSULT_STATUS_REPLIED,
        )

    async def count_doctor_patients(self, doctor_id: int) -> int:
        """本人档案 ∪ 预约 ∪ 问诊的患者去重数（FUNCTIONAL_SPEC 2.9）。

        `union` 已按行去重，外层再 `count(*)` 即得去重后的患者数。"""
        patient_ids = union(
            select(HealthRecordRow.user_id).where(
                HealthRecordRow.doctor_id == doctor_id
            ),
            select(AppointmentRow.user_id).where(
                AppointmentRow.doctor_id == doctor_id
            ),
            select(DoctorConsultRow.user_id).where(
                DoctorConsultRow.doctor_id == doctor_id
            ),
        ).subquery()
        return int(
            (
                await self._session.execute(
                    select(func.count()).select_from(patient_ids)
                )
            ).scalar_one()
        )

    # --- 患者个人概览 ---------------------------------------------------------

    async def count_user_consults(self, user_id: int) -> int:
        return await self._count(DoctorConsultRow, DoctorConsultRow.user_id == user_id)

    async def count_user_appointments(self, user_id: int) -> int:
        return await self._count(AppointmentRow, AppointmentRow.user_id == user_id)

    async def count_user_records(self, user_id: int) -> int:
        return await self._count(HealthRecordRow, HealthRecordRow.user_id == user_id)

    async def count_user_sessions(self, user_id: int) -> int:
        return await self._count(
            ConsultSessionRow, ConsultSessionRow.user_id == user_id
        )

    # --- 趋势 -----------------------------------------------------------------

    async def _per_day(
        self, column, *, start: date, end: date
    ) -> dict[date, int]:
        """把窗口 [start, end] 内的时间戳按 UTC 自然日分桶计数。"""
        lower = datetime.combine(start, time.min)
        upper = datetime.combine(end + timedelta(days=1), time.min)
        values = (
            (
                await self._session.execute(
                    select(column).where(column >= lower, column < upper)
                )
            )
            .scalars()
            .all()
        )
        counts: dict[date, int] = {}
        for value in values:
            day = value.date()
            counts[day] = counts.get(day, 0) + 1
        return counts

    async def session_counts_per_day(
        self, *, start: date, end: date
    ) -> dict[date, int]:
        return await self._per_day(ConsultSessionRow.create_time, start=start, end=end)

    async def user_counts_per_day(self, *, start: date, end: date) -> dict[date, int]:
        return await self._per_day(UserRow.create_time, start=start, end=end)

    # --- 分布 -----------------------------------------------------------------

    async def appointments_by_department(self) -> list[tuple[str, int]]:
        """每个科室的预约数；无预约的科室计 0（FUNCTIONAL_SPEC 2.9）。"""
        departments = (
            (
                await self._session.execute(
                    select(DepartmentRow).order_by(
                        func.coalesce(DepartmentRow.sort_order, 0).asc(),
                        DepartmentRow.id.desc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        counts = dict(
            (
                await self._session.execute(
                    select(AppointmentRow.department_id, func.count()).group_by(
                        AppointmentRow.department_id
                    )
                )
            ).all()
        )
        return [(row.name, int(counts.get(row.id, 0))) for row in departments]

    async def knowledge_type_counts(self) -> list[tuple[str, int]]:
        """按文件类型统计知识文件数，多者在前（FUNCTIONAL_SPEC 2.9）。"""
        counted = func.count()
        rows = (
            await self._session.execute(
                select(KnowledgeFileRow.file_type, counted)
                .group_by(KnowledgeFileRow.file_type)
                .order_by(counted.desc(), KnowledgeFileRow.file_type.asc())
            )
        ).all()
        return [(file_type, int(count)) for file_type, count in rows]
