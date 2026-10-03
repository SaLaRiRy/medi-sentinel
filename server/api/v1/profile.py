"""TICKET-012：个人中心端点（`SPEC.md` 5.4「认证与个人中心」）。

- `GET /profile/info`：返回本人资料，字段按角色不同
- `PUT /profile/update`：更新本人资料（只写该角色真实存在的字段）
- `PUT /profile/password`：改密，原口令错误 → 400
- `POST /profile/avatar`：头像上传，超过配置上限 → 413

四个端点都没有 id 参数，操作对象恒为令牌对应的本人，因此不存在越权访问他人
资料的路径（FUNCTIONAL_SPEC 2.2）。TICKET-014 解除 `contracts/` 冻结后，这四个
端点随生成机制正常进入 `contracts/openapi.json`（C-1 seam）。
"""

import os
import secrets
from pathlib import Path
from typing import Any

import anyio
from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from core.deps import CurrentUser, get_active_settings, get_current_user, get_session
from core.errors import ApiError
from core.response import Envelope, success
from core.security import verify_password
from services.auth_service import display_name_for

router = APIRouter(tags=["profile"])

# The union of the three roles' editable fields; a role only writes the ones its
# own table has (FUNCTIONAL_SPEC 4.3.1-4.3.3).
PROFILE_FIELDS = (
    "real_name",
    "gender",
    "age",
    "allergy_history",
    "phone",
    "nickname",
    "email",
    "department_id",
    "title",
    "specialty",
    "introduction",
)


class ProfileUpdateRequest(BaseModel):
    nickname: str | None = None
    real_name: str | None = None
    phone: str | None = None
    email: str | None = None
    gender: int | None = None
    age: int | None = None
    allergy_history: str | None = None
    title: str | None = None
    specialty: str | None = None
    introduction: str | None = None


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str


class ProfileView(BaseModel):
    id: int
    username: str
    role: str
    display_name: str
    status: int | None = None
    avatar: str | None = None
    real_name: str | None = None
    gender: int | None = None
    age: int | None = None
    allergy_history: str | None = None
    phone: str | None = None
    nickname: str | None = None
    email: str | None = None
    department_id: int | None = None
    title: str | None = None
    specialty: str | None = None
    introduction: str | None = None

    @classmethod
    def of(cls, user: CurrentUser) -> "ProfileView":
        row = user.row
        fields: dict[str, Any] = {
            "id": user.user_id,
            "username": user.username,
            "role": user.role,
            "display_name": display_name_for(user.role, row),
            "status": row.status,
            "avatar": row.avatar,
        }
        for name in PROFILE_FIELDS:
            if hasattr(row, name):
                fields[name] = getattr(row, name)
        return cls(**fields)


class AvatarView(BaseModel):
    avatar: str


@router.get(
    "/profile/info",
    response_model=Envelope[ProfileView],
    response_model_exclude_unset=True,
)
async def read_profile(
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[ProfileView]:
    return success(ProfileView.of(user))


@router.put(
    "/profile/update",
    response_model=Envelope[None],
)
async def update_profile(
    payload: ProfileUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[None]:
    for name, value in payload.model_dump(exclude_unset=True).items():
        if hasattr(user.row, name):
            setattr(user.row, name, value)
    return success(None)


@router.put(
    "/profile/password",
    response_model=Envelope[None],
)
async def change_password(
    payload: PasswordChangeRequest,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Envelope[None]:
    if not verify_password(payload.old_password, user.row.password):
        raise ApiError(400, "原密码错误")
    user.row.password = payload.new_password
    return success(None)


@router.post(
    "/profile/avatar",
    response_model=Envelope[AvatarView],
)
async def upload_avatar(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    settings: Settings = Depends(get_active_settings),
    session: AsyncSession = Depends(get_session),
) -> Envelope[AvatarView]:
    content = await file.read()
    if len(content) > settings.avatar_max_bytes:
        raise ApiError(413, "文件超过大小上限")
    stored_name = secrets.token_hex(16) + os.path.splitext(file.filename or "")[1]
    directory = Path(settings.upload_dir) / settings.avatar_subdir
    await anyio.to_thread.run_sync(lambda: directory.mkdir(parents=True, exist_ok=True))
    await anyio.to_thread.run_sync((directory / stored_name).write_bytes, content)
    avatar = f"{settings.uploads_url_prefix}/{settings.avatar_subdir}/{stored_name}"
    user.row.avatar = avatar
    return success(AvatarView(avatar=avatar))
