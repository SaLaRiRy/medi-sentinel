"""TICKET-020：科室主数据端点（`SPEC.md` 5.4「患者与医生主数据」）。

- `GET /departments`：公开列表，只读状态为 1，按 `sort_order` 升序、同值倒序
- `GET /departments/admin`：管理员分页，含全部状态
- `POST /departments` / `PUT /departments/{id}`：名称唯一由应用层保证（409）
- `DELETE /departments/{id}`：仍有关联医生时 409 且不落库（`FUNCTIONAL_SPEC.md` 5.12）
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
from core.serialization import ApiDateTime
from models.department import (
    DEPARTMENT_DESCRIPTION_MAX_LENGTH,
    DEPARTMENT_NAME_MAX_LENGTH,
)
from repositories.departments import DepartmentRecord, DepartmentRepository

router = APIRouter(tags=["departments"])


class DepartmentRequest(BaseModel):
    """`SPEC.md` 5.3：`DepartmentRequest`。"""

    name: str = Field(min_length=1, max_length=DEPARTMENT_NAME_MAX_LENGTH)
    description: str | None = Field(
        default=None, max_length=DEPARTMENT_DESCRIPTION_MAX_LENGTH
    )
    sort_order: int = 0


class DepartmentCreatedView(BaseModel):
    id: int


class DepartmentView(BaseModel):
    id: int
    name: str
    description: str | None = None
    sort_order: int = 0
    status: int = 1
    doctor_count: int = 0
    create_time: ApiDateTime | None = None
    update_time: ApiDateTime | None = None

    @classmethod
    def of(cls, record: DepartmentRecord) -> "DepartmentView":
        row = record.row
        return cls(
            id=row.id,
            name=row.name,
            description=row.description,
            sort_order=row.sort_order if row.sort_order is not None else 0,
            status=row.status,
            doctor_count=record.doctor_count,
            create_time=row.create_time,
            update_time=row.update_time,
        )


@router.get("/departments", response_model=Envelope[list[DepartmentView]])
async def list_departments(
    session: AsyncSession = Depends(get_session),
) -> Envelope[list[DepartmentView]]:
    records = await DepartmentRepository(session).list_public()
    return success([DepartmentView.of(record) for record in records])


@router.get(
    "/departments/admin",
    response_model=Envelope[PagePayload[DepartmentView]],
    responses=error_responses(401, 403, 422),
)
async def admin_departments(
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Envelope[PagePayload[DepartmentView]]:
    records, total = await DepartmentRepository(session).list_page(
        offset=(page - 1) * page_size, limit=page_size, keyword=keyword
    )
    return page_result(
        [DepartmentView.of(record) for record in records],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/departments",
    response_model=Envelope[DepartmentCreatedView],
    responses=error_responses(401, 403, 409, 422),
)
async def create_department(
    payload: DepartmentRequest,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[DepartmentCreatedView]:
    repository = DepartmentRepository(session)
    if await repository.find_by_name(payload.name) is not None:
        raise ApiError(409, "科室名已存在")
    record = await repository.create(
        name=payload.name,
        description=payload.description,
        sort_order=payload.sort_order,
    )
    return success(DepartmentCreatedView(id=record.row.id))


@router.put(
    "/departments/{department_id}",
    response_model=Envelope[None],
    responses=error_responses(401, 403, 404, 409, 422),
)
async def update_department(
    department_id: int,
    payload: DepartmentRequest,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[None]:
    repository = DepartmentRepository(session)
    if await repository.find_by_id(department_id) is None:
        raise ApiError(404, "科室不存在")
    if (
        await repository.find_by_name(payload.name, exclude_id=department_id)
        is not None
    ):
        raise ApiError(409, "科室名已存在")
    await repository.update(department_id, payload.model_dump())
    return success(None)


@router.delete(
    "/departments/{department_id}",
    response_model=Envelope[None],
    responses=error_responses(401, 403, 404, 409),
)
async def delete_department(
    department_id: int,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[None]:
    found, doctors = await DepartmentRepository(session).delete(department_id)
    if not found:
        raise ApiError(404, "科室不存在")
    if doctors:
        raise ApiError(409, f"该科室下还有 {doctors} 位医生，无法删除")
    return success(None)
