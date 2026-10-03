"""认证领域逻辑（TICKET-012，规则见 `FUNCTIONAL_SPEC.md` 2.2 / 5.8）。

登录与注册放在服务层：角色到表的映射、口令比对、状态判定与令牌签发都是业务
规则，路由只做装配与响应封装。
"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import ApiError
from core.roles import ROLES, ROLE_ADMIN, ROLE_USER
from core.security import create_access_token, verify_password
from repositories.accounts import AccountRepository, AccountRow


@dataclass(frozen=True)
class AuthResult:
    """What a successful login/registration hands back (SPEC.md 5.3 `TokenResponse`)."""

    access_token: str
    role: str
    user_id: int
    username: str
    display_name: str
    avatar: str | None


def display_name_for(role: str, row: AccountRow) -> str:
    """展示名：管理员取昵称，医生/患者取真名，缺失时回退登录名。"""
    if role == ROLE_ADMIN:
        return row.nickname or row.username
    return getattr(row, "real_name", None) or row.username


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._accounts = AccountRepository(session)

    async def login(self, *, username: str, password: str, role: str) -> AuthResult:
        if role not in ROLES:
            raise ApiError(400, "无效的角色类型")
        row = await self._accounts.find_by_username(role, username)
        if row is None or not verify_password(password, row.password):
            raise ApiError(401, "用户名或密码错误")
        if row.status == 0:
            raise ApiError(403, "账号已被禁用")
        return self._issue(role, row)

    async def register(
        self,
        *,
        username: str,
        password: str,
        confirm_password: str,
        real_name: str | None,
        phone: str | None,
    ) -> AuthResult:
        if password != confirm_password:
            raise ApiError(400, "两次密码输入不一致")
        if await self._accounts.find_by_username(ROLE_USER, username) is not None:
            raise ApiError(409, "用户名已存在")
        # 性别强制为 1，状态取默认 1（FUNCTIONAL_SPEC 5.8「注册规则」）。
        row = await self._accounts.create_user(
            username=username,
            password=password,
            real_name=real_name,
            phone=phone,
            gender=1,
            status=1,
        )
        return self._issue(ROLE_USER, row)

    def _issue(self, role: str, row: AccountRow) -> AuthResult:
        token = create_access_token(
            {"sub": row.username, "user_id": row.id, "role": role}
        )
        return AuthResult(
            access_token=token,
            role=role,
            user_id=row.id,
            username=row.username,
            display_name=display_name_for(role, row),
            avatar=row.avatar,
        )
