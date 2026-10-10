"""TICKET-019：人工问诊工单端点（`SPEC.md` 5.4「人工问诊」）。

患者提交工单时可指定医生，也可留空成为「待分配」。抢单语义见
`FUNCTIONAL_SPEC.md` 5.14：工单原本无医生时，首位回复的医生即被写入为负责
医生；已被其他医生认领时返回 409 且不写入回复。主诉的「标题：正文」编码由
前端负责，后端原样存储与回传（`SPEC.md` 5.15 / AC-F-15）。

`GET /consults/{id}/ai-context`（TICKET-AC-05）是闭环的第一段：它把工单指回
AI 会话，让医生看到 AI 已经问出来的候选疾病与引用，而不是让患者重打一遍主诉。
归属校验见该端点的 docstring——它与既有 `GET /chat/sessions/{id}/messages`
**故意不同**（那一条按 `SPEC.md` §7.2「原样保留」不做校验）。
"""

import json

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
from repositories.consult import ASSISTANT_ROLE, ConsultRepository

router = APIRouter(tags=["consults"])


class ConsultCreateRequest(BaseModel):
    doctor_id: int | None = None
    chief_complaint: str = Field(min_length=1)
    #: 关联的 AI 会话号（TICKET-AC-05）。可空：不带会话也能转人工。
    session_id: int | None = None


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


class ConsultAiContextView(BaseModel):
    """工单关联的 AI 上下文（`SPEC.md` 5.4「人工问诊」）。

    `graph` / `references` 用 `list[dict]`：它们就是 SSE `done` 帧里原样落库的那两段
    （`t_consult_message.graph_json` / `references_json`），与 `MessageView` 同形状。
    """

    consult_id: int
    session_id: int | None = None
    chief_complaint: str
    #: 该会话最后一条 AI 回答的全文；没有 AI 回答时为 null。
    summary: str | None = None
    graph: list[dict] = []
    references: list[dict] = []


def _json_list(raw: str | None) -> list[dict]:
    """落库的 JSON 列表，缺失或损坏时回空表（与 `MessageView` 同一口径）。"""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


@router.post(
    "/consults",
    response_model=Envelope[ConsultCreatedView],
    responses=error_responses(401, 403, 404, 422),
)
async def create_consult(
    payload: ConsultCreateRequest,
    principal: Principal = Depends(require_patient),
    session: AsyncSession = Depends(get_session),
) -> Envelope[ConsultCreatedView]:
    if payload.session_id is not None:
        # 只能关联**自己的**会话：不然患者可以拿别人的会话号把医生引到别人的 AI 对话上。
        owned = await ConsultRepository(session).find_session(
            payload.session_id, user_id=principal.user_id
        )
        if owned is None:
            raise ApiError(404, "会话不存在")
    row = await DoctorConsultRepository(session).create(
        user_id=principal.user_id,
        doctor_id=payload.doctor_id,
        chief_complaint=payload.chief_complaint,
        session_id=payload.session_id,
    )
    return success(ConsultCreatedView(id=row.id))


@router.get(
    "/consults/{consult_id}/ai-context",
    response_model=Envelope[ConsultAiContextView],
    responses=error_responses(401, 403, 404),
)
async def consult_ai_context(
    consult_id: int,
    principal: Principal = Depends(require_doctor),
    session: AsyncSession = Depends(get_session),
) -> Envelope[ConsultAiContextView]:
    """医生读取工单关联的 AI 上下文。

    **归属校验（与既有约定故意不同）**：`GET /chat/sessions/{id}/messages` 按
    `SPEC.md` §7.2「原样保留」只校验会话存在、不校验归属（患者读的是自己的会话，
    没有越权面）。本端点面向医生，读的是**被指派 / 待认领工单**指向的会话——
    工单本身就是授权凭证：未认领工单对全体医生可见（`FUNCTIONAL_SPEC.md` 5.14），
    已被他人认领的工单只对负责医生可见。不这样做，任何医生都能凭工单号遍历
    全部患者的 AI 对话。
    """
    repository = DoctorConsultRepository(session)
    row = await repository.find(consult_id)
    if row is None or (row.doctor_id is not None and row.doctor_id != principal.user_id):
        raise ApiError(404, "工单不存在")

    if row.session_id is None:
        # 历史工单 / 不带会话转人工：明确返回空上下文，不是 500。
        return success(
            ConsultAiContextView(
                consult_id=row.id,
                session_id=None,
                chief_complaint=row.chief_complaint,
            )
        )

    consults = ConsultRepository(session)
    session_row = await consults.find_session_by_id(row.session_id)
    if session_row is None:
        # 会话被删：工单仍有效，只是没有上下文。
        return success(
            ConsultAiContextView(
                consult_id=row.id,
                session_id=None,
                chief_complaint=row.chief_complaint,
            )
        )
    if session_row.user_id is not None and session_row.user_id != row.user_id:
        # 工单与会话归属不一致：宁可拒绝，也不把别人的 AI 对话交给医生。
        raise ApiError(404, "AI 上下文不存在")

    messages = await consults.messages(row.session_id)
    latest = next(
        (message for message in reversed(messages) if message.role == ASSISTANT_ROLE),
        None,
    )
    return success(
        ConsultAiContextView(
            consult_id=row.id,
            session_id=row.session_id,
            chief_complaint=row.chief_complaint,
            summary=latest.content if latest is not None else None,
            graph=_json_list(latest.graph_json) if latest is not None else [],
            references=(
                _json_list(latest.references_json) if latest is not None else []
            ),
        )
    )


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
