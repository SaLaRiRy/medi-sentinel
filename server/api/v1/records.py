"""TICKET-018：健康档案端点（`SPEC.md` 5.4「预约与健康档案」）。

- `GET /records/my`：患者查看本人档案
- `GET /records/doctor`：医生查看本人名下的档案
- `GET /records/doctor/patient-options`：建档时可选的病人选项
- `POST /records/doctor`：医生为患者建档；患者不存在返回 404
- `PUT /records/doctor/{id}`：医生修改本人名下的档案；不匹配返回 404
- `DELETE /records/doctor/{id}`：医生删除本人名下的档案；不匹配返回 404

归属校验是硬要求（`FUNCTIONAL_SPEC.md` 5.16）：更新与删除在仓储层就以「档案号
且医生号」过滤，医生碰不到他人名下的档案，且数据不变。越界字段（缺 `record_type`
或超长）由请求 Schema 拒绝并返回 422。

TICKET-AC-06 加了闭环第二段的两个动作：`POST /records/doctor/from-consult`
（医生把工单结论**确认**为档案）与 `POST /records/doctor/{id}/withdraw`（撤回，软删）。
**AI 文本不得直接落病历**：`source='ai'` 只有前一个动作能写，且它要求工单已经
被当前医生认领；同一工单重复确认是幂等的，不会留下第二条档案。
"""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import Principal, get_session, require_doctor, require_patient
from core.errors import ApiError
from core.response import Envelope, error_responses, success
from core.serialization import ApiDate, ApiDateTime
from models.health_record import DIAGNOSIS_MAX_LENGTH, RECORD_TYPE_MAX_LENGTH
from repositories.health_records import HealthRecordRecord, HealthRecordRepository
from repositories.doctor_consults import DoctorConsultRepository

router = APIRouter(tags=["records"])


class HealthRecordCreateRequest(BaseModel):
    user_id: int
    record_type: str = Field(min_length=1, max_length=RECORD_TYPE_MAX_LENGTH)
    diagnosis: str | None = Field(default=None, max_length=DIAGNOSIS_MAX_LENGTH)
    treatment: str | None = None
    prescription: str | None = None
    visit_date: date | None = None


class HealthRecordUpdateRequest(BaseModel):
    """`SPEC.md` 5.3：`HealthRecordCreateRequest` 除 `user_id` 外全部可选。"""

    record_type: str | None = Field(
        default=None, min_length=1, max_length=RECORD_TYPE_MAX_LENGTH
    )
    diagnosis: str | None = Field(default=None, max_length=DIAGNOSIS_MAX_LENGTH)
    treatment: str | None = None
    prescription: str | None = None
    visit_date: date | None = None


class PatientOptionView(BaseModel):
    id: int
    name: str


class HealthRecordView(BaseModel):
    id: int
    user_id: int
    user_name: str | None = None
    doctor_id: int | None = None
    doctor_name: str | None = None
    #: 内容来源与来源工单（TICKET-AC-06），患者端据此显示「来自 AI 建议」。
    source: str = "doctor"
    consult_id: int | None = None
    record_type: str | None = None
    diagnosis: str | None = None
    treatment: str | None = None
    prescription: str | None = None
    visit_date: ApiDate | None = None
    create_time: ApiDateTime | None = None
    update_time: ApiDateTime | None = None

    @classmethod
    def of(cls, record: HealthRecordRecord) -> "HealthRecordView":
        row = record.row
        return cls(
            id=row.id,
            user_id=row.user_id,
            user_name=record.patient_name,
            doctor_id=row.doctor_id,
            doctor_name=record.doctor_name,
            source=row.source,
            consult_id=row.consult_id,
            record_type=row.record_type,
            diagnosis=row.diagnosis,
            treatment=row.treatment,
            prescription=row.prescription,
            visit_date=row.visit_date,
            create_time=row.create_time,
            update_time=row.update_time,
        )


class RecordFromConsultRequest(BaseModel):
    """医生确认把工单结论沉淀为档案（TICKET-AC-06）。

    `source` 只接受 `ai`（医生确认了 AI 建议）与 `doctor`（医生自己的结论）：
    两个值都必须经过本端点的**医生确认动作**才会落库，不存在别的写入口。
    """

    consult_id: int
    record_type: str = Field(min_length=1, max_length=RECORD_TYPE_MAX_LENGTH)
    diagnosis: str | None = Field(default=None, max_length=DIAGNOSIS_MAX_LENGTH)
    treatment: str | None = None
    prescription: str | None = None
    visit_date: date | None = None
    source: Literal["ai", "doctor"] = "doctor"


@router.get(
    "/records/my",
    response_model=Envelope[list[HealthRecordView]],
    responses=error_responses(401, 403),
)
async def my_records(
    principal: Principal = Depends(require_patient),
    session: AsyncSession = Depends(get_session),
) -> Envelope[list[HealthRecordView]]:
    records = await HealthRecordRepository(session).list_for_user(principal.user_id)
    return success([HealthRecordView.of(record) for record in records])


@router.get(
    "/records/doctor",
    response_model=Envelope[list[HealthRecordView]],
    responses=error_responses(401, 403),
)
async def doctor_records(
    principal: Principal = Depends(require_doctor),
    session: AsyncSession = Depends(get_session),
) -> Envelope[list[HealthRecordView]]:
    records = await HealthRecordRepository(session).list_for_doctor(principal.user_id)
    return success([HealthRecordView.of(record) for record in records])


@router.post(
    "/records/doctor",
    response_model=Envelope[HealthRecordView],
    responses=error_responses(401, 403, 404, 422),
)
async def create_record(
    payload: HealthRecordCreateRequest,
    principal: Principal = Depends(require_doctor),
    session: AsyncSession = Depends(get_session),
) -> Envelope[HealthRecordView]:
    record = await HealthRecordRepository(session).create(
        doctor_id=principal.user_id,
        user_id=payload.user_id,
        record_type=payload.record_type,
        diagnosis=payload.diagnosis,
        treatment=payload.treatment,
        prescription=payload.prescription,
        visit_date=payload.visit_date,
    )
    if record is None:
        raise ApiError(404, "患者不存在")
    return success(HealthRecordView.of(record))


@router.get(
    "/records/doctor/patient-options",
    response_model=Envelope[list[PatientOptionView]],
    responses=error_responses(401, 403),
)
async def record_patient_options(
    principal: Principal = Depends(require_doctor),
    session: AsyncSession = Depends(get_session),
) -> Envelope[list[PatientOptionView]]:
    options = await HealthRecordRepository(session).patient_options(principal.user_id)
    return success(
        [PatientOptionView(id=option.id, name=option.name) for option in options]
    )


@router.post(
    "/records/doctor/from-consult",
    response_model=Envelope[HealthRecordView],
    responses=error_responses(401, 403, 404, 422),
)
async def create_record_from_consult(
    payload: RecordFromConsultRequest,
    principal: Principal = Depends(require_doctor),
    session: AsyncSession = Depends(get_session),
) -> Envelope[HealthRecordView]:
    """把一张**已认领工单**的结论沉淀为档案（幂等）。

    未认领或属于其他医生的工单一律 404：沉淀的前提是这位医生确实负责这张工单。
    同一工单重复确认返回已有的那条，不产生第二条档案。
    """
    consult = await DoctorConsultRepository(session).find(payload.consult_id)
    if consult is None or consult.doctor_id != principal.user_id:
        raise ApiError(404, "工单不存在")

    repository = HealthRecordRepository(session)
    existing = await repository.find_by_consult(payload.consult_id, principal.user_id)
    if existing is not None:
        return success(HealthRecordView.of(existing))

    record = await repository.create(
        doctor_id=principal.user_id,
        user_id=consult.user_id,
        record_type=payload.record_type,
        diagnosis=payload.diagnosis,
        treatment=payload.treatment,
        prescription=payload.prescription,
        visit_date=payload.visit_date,
        source=payload.source,
        consult_id=payload.consult_id,
    )
    if record is None:
        raise ApiError(404, "患者不存在")
    return success(HealthRecordView.of(record))


@router.post(
    "/records/doctor/{record_id}/withdraw",
    response_model=Envelope[None],
    responses=error_responses(401, 403, 404),
)
async def withdraw_record(
    record_id: int,
    principal: Principal = Depends(require_doctor),
    session: AsyncSession = Depends(get_session),
) -> Envelope[None]:
    """撤回本医生名下的档案（软删，`withdrawn = 1`）：行保留，只是不再出现在列表里。"""
    withdrawn = await HealthRecordRepository(session).withdraw(
        record_id, principal.user_id
    )
    if not withdrawn:
        raise ApiError(404, "档案不存在")
    return success(None)


@router.put(
    "/records/doctor/{record_id}",
    response_model=Envelope[HealthRecordView],
    responses=error_responses(401, 403, 404, 422),
)
async def update_record(
    record_id: int,
    payload: HealthRecordUpdateRequest,
    principal: Principal = Depends(require_doctor),
    session: AsyncSession = Depends(get_session),
) -> Envelope[HealthRecordView]:
    record = await HealthRecordRepository(session).update(
        record_id, principal.user_id, payload.model_dump(exclude_unset=True)
    )
    if record is None:
        raise ApiError(404, "档案不存在")
    return success(HealthRecordView.of(record))


@router.delete(
    "/records/doctor/{record_id}",
    response_model=Envelope[None],
    responses=error_responses(401, 403, 404),
)
async def delete_record(
    record_id: int,
    principal: Principal = Depends(require_doctor),
    session: AsyncSession = Depends(get_session),
) -> Envelope[None]:
    deleted = await HealthRecordRepository(session).delete(
        record_id, principal.user_id
    )
    if not deleted:
        raise ApiError(404, "档案不存在")
    return success(None)
