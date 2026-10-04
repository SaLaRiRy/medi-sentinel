"""TICKET-019：人工问诊工单端点（`SPEC.md` 5.4「人工问诊」）。

患者提交工单时可指定医生，也可留空成为「待分配」。抢单语义见
`FUNCTIONAL_SPEC.md` 5.14：工单原本无医生时，首位回复的医生即被写入为负责
医生；已被其他医生认领时返回 409 且不写入回复。主诉的「标题：正文」编码由
前端负责，后端原样存储与回传（`SPEC.md` 5.15 / AC-F-15）。
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import (
    Principal,
    get_session,
    require_admin,
    require_doctor,
    require_patient,
)
from core.errors import ApiError
from core.response import Envelope, PagePayload, error_responses, page_result, success
from core.serialization import ApiDateTime
from repositories.doctor_consults import (
    REPLY_CLAIMED,
    REPLY_MISSING,
    ConsultRecord,
    DoctorConsultRepository,
    ReplyRecord,
)

router = APIRouter(tags=["consults"])


class ConsultCreateRequest(BaseModel):
    doctor_id: int | None = None
    chief_complaint: str = Field(min_length=1)


class ConsultReplyRequest(BaseModel):
    """`SPEC.md` 5.3：回复体带 `consult_id` 与 `content`；路径号是操作对象。"""

    consult_id: int
    content: str = Field(min_length=1)


class ConsultCreatedView(BaseModel):
    id: int


class ConsultReplyView(BaseModel):
    id: int
    consult_id: int
    doctor_id: int
    doctor_name: str | None = None
    content: str
    create_time: ApiDateTime | None = None

    @classmethod
    def of(cls, record: ReplyRecord) -> "ConsultReplyView":
        row = record.row
        return cls(
            id=row.id,
            consult_id=row.consult_id,
            doctor_id=row.doctor_id,
            doctor_name=record.doctor_name,
            content=row.content,
            create_time=row.create_time,
        )


class ConsultView(BaseModel):
    id: int
    user_id: int
    user_name: str | None = None
    doctor_id: int | None = None
    doctor_name: str | None = None
    chief_complaint: str
    status: int
    create_time: ApiDateTime | None = None
    update_time: ApiDateTime | None = None
    replies: list[ConsultReplyView] = []

    @classmethod
    def of(cls, record: ConsultRecord) -> "ConsultView":
        row = record.row
        return cls(
            id=row.id,
            user_id=row.user_id,
            user_name=record.patient_name,
            doctor_id=row.doctor_id,
            doctor_name=record.doctor_name,
            chief_complaint=row.chief_complaint,
            status=row.status,
            create_time=row.create_time,
            update_time=row.update_time,
            replies=[ConsultReplyView.of(reply) for reply in record.replies],
        )


@router.post(
    "/consults",
    response_model=Envelope[ConsultCreatedView],
    responses=error_responses(401, 403, 422),
)
async def create_consult(
    payload: ConsultCreateRequest,
    principal: Principal = Depends(require_patient),
    session: AsyncSession = Depends(get_session),
) -> Envelope[ConsultCreatedView]:
    row = await DoctorConsultRepository(session).create(
        user_id=principal.user_id,
        doctor_id=payload.doctor_id,
        chief_complaint=payload.chief_complaint,
    )
    return success(ConsultCreatedView(id=row.id))


@router.get(
    "/consults/my",
    response_model=Envelope[list[ConsultView]],
    responses=error_responses(401, 403),
)
async def my_consults(
    principal: Principal = Depends(require_patient),
    session: AsyncSession = Depends(get_session),
) -> Envelope[list[ConsultView]]:
    records = await DoctorConsultRepository(session).list_for_user(principal.user_id)
    return success([ConsultView.of(record) for record in records])


@router.get(
    "/consults/pending",
    response_model=Envelope[list[ConsultView]],
    responses=error_responses(401, 403),
)
async def pending_consults(
    principal: Principal = Depends(require_doctor),
    session: AsyncSession = Depends(get_session),
) -> Envelope[list[ConsultView]]:
    records = await DoctorConsultRepository(session).list_pending(principal.user_id)
    return success([ConsultView.of(record) for record in records])


@router.post(
    "/consults/{consult_id}/replies",
    response_model=Envelope[None],
    responses=error_responses(401, 403, 404, 409, 422),
)
async def reply_consult(
    consult_id: int,
    payload: ConsultReplyRequest,
    principal: Principal = Depends(require_doctor),
    session: AsyncSession = Depends(get_session),
) -> Envelope[None]:
    outcome = await DoctorConsultRepository(session).reply(
        consult_id, doctor_id=principal.user_id, content=payload.content
    )
    if outcome == REPLY_MISSING:
        raise ApiError(404, "工单不存在")
    if outcome == REPLY_CLAIMED:
        raise ApiError(409, "该工单已被其他医生认领")
    return success(None)


@router.get(
    "/consults/admin",
    response_model=Envelope[PagePayload[ConsultView]],
    responses=error_responses(401, 403, 422),
)
async def admin_consults(
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    status: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Envelope[PagePayload[ConsultView]]:
    records, total = await DoctorConsultRepository(session).list_page(
        offset=(page - 1) * page_size, limit=page_size, status=status
    )
    return page_result(
        [ConsultView.of(record) for record in records],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.delete(
    "/consults/admin/{consult_id}",
    response_model=Envelope[None],
    responses=error_responses(401, 403, 404),
)
async def delete_consult(
    consult_id: int,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[None]:
    deleted = await DoctorConsultRepository(session).delete(consult_id)
    if not deleted:
        raise ApiError(404, "工单不存在")
    return success(None)
