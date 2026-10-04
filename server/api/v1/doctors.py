"""TICKET-020：医生主数据端点（`SPEC.md` 5.4「患者与医生主数据」）。

- `GET /doctors`：公开列表，只显示状态为 1 且已分配科室的医生，可按科室过滤
- `GET /doctors/admin`：管理员分页，显示全部状态
- `POST /doctors` / `PUT /doctors/{id}`：用户名重复 409、两次口令不一致 400
- `DELETE /doctors/{id}`：级联清理后删除医生（`FUNCTIONAL_SPEC.md` 5.11）
- `PUT /doctors/{id}/status`：直接写入状态值（无迁移校验）

科室引用是逻辑编号，本模块不校验科室是否存在（`FUNCTIONAL_SPEC.md` 4.4）。
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import Principal, get_session, require_admin
from core.errors import ApiError
from core.response import (
    Envelope,
    PagePayload,
    error_responses,
    page_result,
    success,
)
from core.roles import ROLE_DOCTOR
from core.serialization import ApiDateTime
from models.accounts import USERNAME_MAX_LENGTH
from repositories.accounts import AccountRepository
from repositories.doctors import DoctorDirectoryRepository, DoctorRecord
from services.passwords import ensure_password_confirmation

router = APIRouter(tags=["doctors"])


class DoctorCreateRequest(BaseModel):
    """`SPEC.md` 5.3：`DoctorCreateRequest`。"""

    username: str = Field(min_length=3, max_length=USERNAME_MAX_LENGTH)
    password: str = Field(min_length=6)
    confirm_password: str = Field(min_length=6)
    real_name: str = Field(min_length=1, max_length=50)
    department_id: int | None = None
    title: str | None = None
    specialty: str | None = None
    introduction: str | None = None
    phone: str | None = Field(default=None, max_length=20)
    status: int = 1


class DoctorUpdateRequest(BaseModel):
    """`SPEC.md` 5.3：`DoctorUpdateRequest`（除 `username` 外可选，另含口令）。"""

    password: str | None = None
    confirm_password: str | None = None
    real_name: str | None = Field(default=None, min_length=1, max_length=50)
    department_id: int | None = None
    title: str | None = None
    specialty: str | None = None
    introduction: str | None = None
    phone: str | None = Field(default=None, max_length=20)
    status: int | None = None


class DoctorStatusRequest(BaseModel):
    status: int


class DoctorView(BaseModel):
    id: int
    username: str
    real_name: str
    department_id: int | None = None
    department_name: str | None = None
    title: str | None = None
    specialty: str | None = None
    introduction: str | None = None
    phone: str | None = None
    avatar: str | None = None
    status: int | None = None
    create_time: ApiDateTime | None = None
    update_time: ApiDateTime | None = None

    @classmethod
    def of(cls, record: DoctorRecord) -> "DoctorView":
        row = record.row
        return cls(
            id=row.id,
            username=row.username,
            real_name=row.real_name,
            department_id=row.department_id,
            department_name=record.department_name,
            title=row.title,
            specialty=row.specialty,
            introduction=row.introduction,
            phone=row.phone,
            avatar=row.avatar,
            status=row.status,
            create_time=row.create_time,
            update_time=row.update_time,
        )


def _update_fields(payload: DoctorUpdateRequest) -> dict:
    """Handle the confirmation and reject nulling the NOT NULL `real_name`."""
    fields = payload.model_dump(exclude_unset=True)
    confirm = fields.pop("confirm_password", None)
    password = fields.get("password")
    if password is None:
        fields.pop("password", None)
    else:
        ensure_password_confirmation(password, confirm)
    if "real_name" in fields and fields["real_name"] is None:
        raise ApiError(422, "姓名不能为空")
    return fields


@router.get(
    "/doctors",
    response_model=Envelope[PagePayload[DoctorView]],
    responses=error_responses(422),
)
async def list_doctors(
    session: AsyncSession = Depends(get_session),
    department_id: int | None = None,
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Envelope[PagePayload[DoctorView]]:
    records, total = await DoctorDirectoryRepository(session).list_public(
        offset=(page - 1) * page_size,
        limit=page_size,
        department_id=department_id,
        keyword=keyword,
    )
    return page_result(
        [DoctorView.of(record) for record in records],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/doctors/admin",
    response_model=Envelope[PagePayload[DoctorView]],
    responses=error_responses(401, 403, 422),
)
async def admin_doctors(
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Envelope[PagePayload[DoctorView]]:
    records, total = await DoctorDirectoryRepository(session).list_page(
        offset=(page - 1) * page_size, limit=page_size, keyword=keyword
    )
    return page_result(
        [DoctorView.of(record) for record in records],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/doctors",
    response_model=Envelope[DoctorView],
    responses=error_responses(400, 401, 403, 409, 422),
)
async def create_doctor(
    payload: DoctorCreateRequest,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[DoctorView]:
    ensure_password_confirmation(payload.password, payload.confirm_password)
    accounts = AccountRepository(session)
    if await accounts.find_by_username(ROLE_DOCTOR, payload.username) is not None:
        raise ApiError(409, "用户名已存在")
    row = await accounts.create(
        ROLE_DOCTOR,
        username=payload.username,
        password=payload.password,
        real_name=payload.real_name,
        department_id=payload.department_id,
        title=payload.title,
        specialty=payload.specialty,
        introduction=payload.introduction,
        phone=payload.phone,
        status=payload.status,
    )
    record = await DoctorDirectoryRepository(session).find_by_id(row.id)
    return success(DoctorView.of(record))


@router.put(
    "/doctors/{doctor_id}",
    response_model=Envelope[DoctorView],
    responses=error_responses(400, 401, 403, 404, 422),
)
async def update_doctor(
    doctor_id: int,
    payload: DoctorUpdateRequest,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[DoctorView]:
    fields = _update_fields(payload)
    row = await AccountRepository(session).update(ROLE_DOCTOR, doctor_id, fields)
    if row is None:
        raise ApiError(404, "医生不存在")
    record = await DoctorDirectoryRepository(session).find_by_id(row.id)
    return success(DoctorView.of(record))


@router.put(
    "/doctors/{doctor_id}/status",
    response_model=Envelope[None],
    responses=error_responses(401, 403, 404, 422),
)
async def update_doctor_status(
    doctor_id: int,
    payload: DoctorStatusRequest,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[None]:
    updated = await AccountRepository(session).set_status(
        ROLE_DOCTOR, doctor_id, payload.status
    )
    if not updated:
        raise ApiError(404, "医生不存在")
    return success(None)


@router.delete(
    "/doctors/{doctor_id}",
    response_model=Envelope[None],
    responses=error_responses(401, 403, 404),
)
async def delete_doctor(
    doctor_id: int,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[None]:
    deleted = await AccountRepository(session).delete(ROLE_DOCTOR, doctor_id)
    if not deleted:
        raise ApiError(404, "医生不存在")
    return success(None)
