"""TICKET-020：患者主数据端点（`SPEC.md` 5.4「患者与医生主数据」）。

- `GET /users`：管理员分页，可选关键字检索
- `POST /users`：管理员建患者，用户名重复 409、两次口令不一致 400
- `PUT /users/{id}`：改资料；提供新口令时校验确认口令
- `DELETE /users/{id}`：级联清理后删除患者（`FUNCTIONAL_SPEC.md` 5.11 / AC-E-08）
- `PUT /users/{id}/status`：直接写入状态值（无迁移校验）

口令以明文存取（`FUNCTIONAL_SPEC.md` 5.8），错误码承载在真实 HTTP 状态码上。
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
from core.roles import ROLE_USER
from core.serialization import ApiDateTime
from models.accounts import USERNAME_MAX_LENGTH, UserRow
from repositories.accounts import AccountRepository
from services.passwords import ensure_password_confirmation

router = APIRouter(tags=["users"])


class UserCreateRequest(BaseModel):
    """`SPEC.md` 5.3：`UserCreateRequest`。"""

    username: str = Field(min_length=3, max_length=USERNAME_MAX_LENGTH)
    password: str = Field(min_length=6)
    confirm_password: str = Field(min_length=6)
    real_name: str | None = None
    gender: int = 1
    age: int | None = None
    phone: str | None = Field(default=None, max_length=20)
    allergy_history: str | None = None
    status: int = 1


class UserUpdateRequest(BaseModel):
    """`SPEC.md` 5.3：`UserUpdateRequest`（除 `username` 外全部可选，另含口令）。"""

    password: str | None = None
    confirm_password: str | None = None
    real_name: str | None = None
    gender: int | None = None
    age: int | None = None
    phone: str | None = Field(default=None, max_length=20)
    allergy_history: str | None = None
    status: int | None = None


class UserStatusRequest(BaseModel):
    status: int


class UserView(BaseModel):
    id: int
    username: str
    real_name: str | None = None
    gender: int | None = None
    age: int | None = None
    phone: str | None = None
    avatar: str | None = None
    allergy_history: str | None = None
    status: int | None = None
    create_time: ApiDateTime | None = None
    update_time: ApiDateTime | None = None

    @classmethod
    def of(cls, row: UserRow) -> "UserView":
        return cls(
            id=row.id,
            username=row.username,
            real_name=row.real_name,
            gender=row.gender,
            age=row.age,
            phone=row.phone,
            avatar=row.avatar,
            allergy_history=row.allergy_history,
            status=row.status,
            create_time=row.create_time,
            update_time=row.update_time,
        )


def _update_fields(payload: UserUpdateRequest) -> dict:
    """Drop the confirmation and turn an explicit `password: null` into no-op."""
    fields = payload.model_dump(exclude_unset=True)
    confirm = fields.pop("confirm_password", None)
    password = fields.get("password")
    if password is None:
        fields.pop("password", None)
    else:
        ensure_password_confirmation(password, confirm)
    return fields


@router.get(
    "/users",
    response_model=Envelope[PagePayload[UserView]],
    responses=error_responses(401, 403, 422),
)
async def list_users(
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    keyword: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Envelope[PagePayload[UserView]]:
    rows, total = await AccountRepository(session).list_page(
        ROLE_USER,
        offset=(page - 1) * page_size,
        limit=page_size,
        keyword=keyword,
    )
    return page_result(
        [UserView.of(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/users",
    response_model=Envelope[UserView],
    responses=error_responses(400, 401, 403, 409, 422),
)
async def create_user(
    payload: UserCreateRequest,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[UserView]:
    ensure_password_confirmation(payload.password, payload.confirm_password)
    repository = AccountRepository(session)
    if await repository.find_by_username(ROLE_USER, payload.username) is not None:
        raise ApiError(409, "用户名已存在")
    row = await repository.create(
        ROLE_USER,
        username=payload.username,
        password=payload.password,
        real_name=payload.real_name,
        gender=payload.gender,
        age=payload.age,
        phone=payload.phone,
        allergy_history=payload.allergy_history,
        status=payload.status,
    )
    return success(UserView.of(row))


@router.put(
    "/users/{user_id}",
    response_model=Envelope[UserView],
    responses=error_responses(400, 401, 403, 404, 422),
)
async def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[UserView]:
    fields = _update_fields(payload)
    row = await AccountRepository(session).update(ROLE_USER, user_id, fields)
    if row is None:
        raise ApiError(404, "用户不存在")
    return success(UserView.of(row))


@router.put(
    "/users/{user_id}/status",
    response_model=Envelope[None],
    responses=error_responses(401, 403, 404, 422),
)
async def update_user_status(
    user_id: int,
    payload: UserStatusRequest,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[None]:
    updated = await AccountRepository(session).set_status(
        ROLE_USER, user_id, payload.status
    )
    if not updated:
        raise ApiError(404, "用户不存在")
    return success(None)


@router.delete(
    "/users/{user_id}",
    response_model=Envelope[None],
    responses=error_responses(401, 403, 404),
)
async def delete_user(
    user_id: int,
    principal: Principal = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> Envelope[None]:
    deleted = await AccountRepository(session).delete(ROLE_USER, user_id)
    if not deleted:
        raise ApiError(404, "用户不存在")
    return success(None)
