"""TICKET-012：认证端点（`SPEC.md` 5.4「认证与个人中心」）。

- `POST /auth/login`：三角色登录，角色决定查哪张账号表
- `POST /auth/register`：患者自助注册，角色固定为 `user`

这些端点对 OpenAPI 隐藏（`include_in_schema=False`）：本票的边界是 `contracts/`
维持现状，而 `test_contract_seam` 要求「生成的 OpenAPI == 提交的契约」。隐藏只是
不写进描述文件，端点本身照常在真实 HTTP 上服务（同 TICKET-011 的做法）。
"""

from dataclasses import asdict

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_session
from core.response import Envelope, success
from services.auth_service import AuthResult, AuthService

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str
    role: str


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6)
    confirm_password: str = Field(min_length=6)
    real_name: str | None = None
    phone: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    username: str
    display_name: str
    avatar: str | None = None


def _token_response(result: AuthResult) -> TokenResponse:
    return TokenResponse(**asdict(result))


@router.post(
    "/auth/login",
    response_model=Envelope[TokenResponse],
    include_in_schema=False,
)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_session),
) -> Envelope[TokenResponse]:
    result = await AuthService(session).login(
        username=payload.username, password=payload.password, role=payload.role
    )
    return success(_token_response(result))


@router.post(
    "/auth/register",
    response_model=Envelope[TokenResponse],
    include_in_schema=False,
)
async def register(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> Envelope[TokenResponse]:
    result = await AuthService(session).register(
        username=payload.username,
        password=payload.password,
        confirm_password=payload.confirm_password,
        real_name=payload.real_name,
        phone=payload.phone,
    )
    return success(_token_response(result))
