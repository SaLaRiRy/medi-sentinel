"""B-5: 人工问诊工单与医生回复的异步存取（TICKET-019）。

会话拥有交易边界：这里不提交，由 `core.deps.get_session` 决定记录的可见性。
工单与回复、患者名与医生名都在这里拼装成 `ConsultRecord`，供 `ConsultView`
直接消费（`FUNCTIONAL_SPEC.md` 4.3.9 / 4.3.10）。
"""

from dataclasses import dataclass

from sqlalchemy import Select, func, or_, select

from models.accounts import DoctorRow, UserRow
from models.doctor_consult import (
    CONSULT_STATUS_PENDING,
    CONSULT_STATUS_REPLIED,
    DoctorConsultRow,
    DoctorReplyRow,
)
from repositories.base import Repository

#: 回复结果的三态：成功（含认领）/ 工单不存在 / 已被其他医生认领。
REPLY_OK = "ok"
REPLY_MISSING = "missing"
REPLY_CLAIMED = "claimed"


@dataclass(frozen=True)
class ReplyRecord:
    """一条回复加上回复医生名（供视图组装，不落库）。"""

    row: DoctorReplyRow
    doctor_name: str | None


@dataclass(frozen=True)
class ConsultRecord:
    """一张工单加上患者名、医生名与全部回复（供视图组装，不落库）。"""

    row: DoctorConsultRow
    patient_name: str | None
    doctor_name: str | None
    replies: tuple[ReplyRecord, ...] = ()


class DoctorConsultRepository(Repository):
    def _consult_query(self) -> Select:
        """工单行加上患者名与医生名；账号缺失时名称为 `None`，行仍可读。"""
        return (
            select(
                DoctorConsultRow,
                func.coalesce(UserRow.real_name, UserRow.username).label(
                    "patient_name"
                ),
                DoctorRow.real_name.label("doctor_name"),
            )
            .outerjoin(UserRow, UserRow.id == DoctorConsultRow.user_id)
            .outerjoin(DoctorRow, DoctorRow.id == DoctorConsultRow.doctor_id)
        )

    async def _replies_for(
        self, consult_ids: list[int]
    ) -> dict[int, list[ReplyRecord]]:
        if not consult_ids:
            return {}
        result = await self._session.execute(
            select(DoctorReplyRow, DoctorRow.real_name)
            .outerjoin(DoctorRow, DoctorRow.id == DoctorReplyRow.doctor_id)
            .where(DoctorReplyRow.consult_id.in_(consult_ids))
            .order_by(DoctorReplyRow.id.asc())
        )
        grouped: dict[int, list[ReplyRecord]] = {}
        for row, doctor_name in result.all():
            grouped.setdefault(row.consult_id, []).append(
                ReplyRecord(row=row, doctor_name=doctor_name)
            )
        return grouped

    async def _records(self, query: Select) -> list[ConsultRecord]:
        rows = (await self._session.execute(query)).all()
        replies = await self._replies_for([row[0].id for row in rows])
        return [
            ConsultRecord(
                row=row,
                patient_name=patient_name,
                doctor_name=doctor_name,
                replies=tuple(replies.get(row.id, ())),
            )
            for row, patient_name, doctor_name in rows
        ]

    async def create(
        self, *, user_id: int, doctor_id: int | None, chief_complaint: str
    ) -> DoctorConsultRow:
        """落库一张工单，状态取默认 0「待回复」（FUNCTIONAL_SPEC.md 4.3.9）。"""
        row = DoctorConsultRow(
            user_id=user_id,
            doctor_id=doctor_id,
            chief_complaint=chief_complaint,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def list_for_user(self, user_id: int) -> list[ConsultRecord]:
        """患者本人的全部工单及其全部回复，新提交的在前（FUNCTIONAL_SPEC 5.14）。"""
        return await self._records(
            self._consult_query()
            .where(DoctorConsultRow.user_id == user_id)
            .order_by(DoctorConsultRow.id.desc())
        )

    async def list_pending(self, doctor_id: int) -> list[ConsultRecord]:
        """指派给我 **或** 尚未指派，且状态为 0（FUNCTIONAL_SPEC 5.14）。"""
        return await self._records(
            self._consult_query()
            .where(
                or_(
                    DoctorConsultRow.doctor_id == doctor_id,
                    DoctorConsultRow.doctor_id.is_(None),
                ),
                DoctorConsultRow.status == CONSULT_STATUS_PENDING,
            )
            .order_by(DoctorConsultRow.id.asc())
        )

    async def reply(
        self, consult_id: int, *, doctor_id: int, content: str
    ) -> str:
        """认领并回复：无医生则写入当前医生；已有其他医生则 409 且不写回复。"""
        row = await self._session.get(DoctorConsultRow, consult_id)
        if row is None:
            return REPLY_MISSING
        if row.doctor_id is not None and row.doctor_id != doctor_id:
            return REPLY_CLAIMED
        if row.doctor_id is None:
            row.doctor_id = doctor_id
        row.status = CONSULT_STATUS_REPLIED
        self._session.add(
            DoctorReplyRow(consult_id=consult_id, doctor_id=doctor_id, content=content)
        )
        await self._session.flush()
        return REPLY_OK

    def _admin_criteria(self, status: int | None) -> list:
        criteria = []
        if status is not None:
            criteria.append(DoctorConsultRow.status == status)
        return criteria

    async def list_page(
        self, *, offset: int, limit: int, status: int | None = None
    ) -> tuple[list[ConsultRecord], int]:
        """管理员分页列表，可按状态过滤（SPEC.md 5.4「人工问诊」）。"""
        criteria = self._admin_criteria(status)
        total = int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(DoctorConsultRow)
                    .where(*criteria)
                )
            ).scalar_one()
        )
        records = await self._records(
            self._consult_query()
            .where(*criteria)
            .order_by(DoctorConsultRow.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return records, total

    async def delete(self, consult_id: int) -> bool:
        """删除工单：先删该工单全部回复，再删工单（FUNCTIONAL_SPEC 5.11）。"""
        row = await self._session.get(DoctorConsultRow, consult_id)
        if row is None:
            return False
        replies = (
            (
                await self._session.execute(
                    select(DoctorReplyRow).where(
                        DoctorReplyRow.consult_id == consult_id
                    )
                )
            )
            .scalars()
            .all()
        )
        for reply in replies:
            await self._session.delete(reply)
        await self._session.delete(row)
        return True
