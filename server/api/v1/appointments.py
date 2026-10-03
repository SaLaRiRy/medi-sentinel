"""TICKET-017：预约挂号端点（`SPEC.md` 5.4「预约与健康档案」）。

- `POST /appointments`：患者提交预约，落库状态取默认 0「待确认」
- `GET /appointments/my`：患者查看本人预约
- `GET /appointments/doctor`：医生查看本人排期（医生号取令牌中的 `user_id`）
- `GET /appointments/admin`：管理员分页查看，可按科室、日期、状态与关键字过滤
- `PUT /appointments/{id}/status`：管理员与医生更新状态；记录不存在返回 404
- `DELETE /appointments/admin/{id}`：仅管理员删除；记录不存在返回 404

状态的写入不做迁移校验（`SPEC.md` 7.3 保留现状）：请求给什么值就写什么值，
只有「记录不存在」从原来的成功返回收紧为 404（`FUNCTIONAL_SPEC.md` 附录 B.3）。
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import (
    Principal,
    get_session,
    require_admin,
    require_doctor,
    require_doctor_or_admin,
    require_patient,
)
from core.errors import ApiError
from core.response import Envelope, PagePayload, page_result, success
from core.serialization import ApiDate, ApiDateTime
from models.appointment import REMARK_MAX_LENGTH, TIME_SLOT_MAX_LENGTH
from repositories.appointments import AppointmentRecord, AppointmentRepository

router = APIRouter(tags=["appointments"])


class AppointmentCreateRequest(BaseModel):
    doctor_id: int
    department_id: int
    visit_date: date
    time_slot: str = Field(max_length=TIME_SLOT_MAX_LENGTH)
    remark: str | None = Field(default=None, max_length=REMARK_MAX_LENGTH)


class AppointmentCreatedView(BaseModel):
    id: int


class AppointmentStatusRequest(BaseModel):
    status: int


class AppointmentView(BaseModel):
    id: int
    user_id: int
    user_name: str | None = None
    doctor_id: int
    doctor_name: str | None = None
    department_id: int
    visit_date: ApiDate
    time_slot: str
    status: int
    remark: str | None = None
    create_time: ApiDateTime | None = None
    update_time: ApiDateTime | None = None

    @classmethod
    def of(cls, record: AppointmentRecord) -> "AppointmentView":
        row = record.row
        return cls(
            id=row.id,
            user_id=row.user_id,
            user_name=record.patient_name,
            doctor_id=row.doctor_id,
            doctor_name=record.doctor_name,
            department_id=row.department_id,
            visit_date=row.visit_date,
            time_slot=row.time_slot,
            status=row.status,
            remark=row.remark,
            create_time=row.create_time,
            update_time=row.update_time,
        )


@router.post(
    "/appointments",
    response_model=Envelope[AppointmentCreatedView],
)
async def create_appointment(
    payload: AppointmentCreateRequest,
    principal: Principal = Depends(require_patient),
    session: AsyncSession = Depends(get_session),
) -> Envelope[AppointmentCreatedView]:
    row = await AppointmentRepository(session).create(
        user_id=principal.user_id,
        doctor_id=payload.doctor_id,
        department_id=payload.department_id,
        visit_date=payload.visit_date,
        time_slot=payload.time_slot,
        remark=payload.remark,
    )
    return success(AppointmentCreatedView(id=row.id))


@router.get(
    "/appointments/my",
    response_model=Envelope[list[AppointmentView]],
)
async def my_appointments(
    principal: Principal = Depends(require_patient),
    session: AsyncSession = Depends(get_session),
) -> Envelope[list[AppointmentView]]:
    records = await AppointmentRepository(session).list_for_user(principal.user_id)
    return success([AppointmentView.of(record) for record in records])


@router.get(
    "/appointments/doctor",
    response_model=Envelope[list[AppointmentView]],
)
async def doctor_appointments(
    principal: Principal = Depends(require_doctor),
    session: AsyncSession = Depends(get_session),
) -> Envelope[list[AppointmentView]]:
    records = await AppointmentRepository(session).list_for_doctor(principal.user_id)
    return success([AppointmentView.of(record) for record in records])


@router.get(
    "/appointments/admin",
    response_model=Envelope[PagePayload[AppointmentView]],
)
async def admin_appointments(
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    keyword: str | None = None,
    department_id: int | None = None,
    visit_date: date | None = None,
    status: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Envelope[PagePayload[AppointmentView]]:
    records, total = await AppointmentRepository(session).list_page(
        offset=(page - 1) * page_size,
        limit=page_size,
        keyword=keyword,
        department_id=department_id,
        visit_date=visit_date,
        status=status,
    )
    return page_result(
        [AppointmentView.of(record) for record in records],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.put(
    "/appointments/{appointment_id}/status",
    response_model=Envelope[None],
)
async def update_appointment_status(
    appointment_id: int,
    payload: AppointmentStatusRequest,
    principal: Principal = Depends(require_doctor_or_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[None]:
    updated = await AppointmentRepository(session).update_status(
        appointment_id, payload.status
    )
    if not updated:
        raise ApiError(404, "预约不存在")
    return success(None)


@router.delete(
    "/appointments/admin/{appointment_id}",
    response_model=Envelope[None],
)
async def delete_appointment(
    appointment_id: int,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[None]:
    deleted = await AppointmentRepository(session).delete(appointment_id)
    if not deleted:
        raise ApiError(404, "预约不存在")
    return success(None)
