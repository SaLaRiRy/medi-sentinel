"""FastAPI dependencies: the B-5 session, the running settings, and the token seam.

The token contract that TICKET-011 deferred lives here: the `Authorization:
Bearer <jwt>` header is decoded, its `role` claim picks the account table, and
the row is loaded before any handler runs. Every failure mode has its documented
status (FUNCTIONAL_SPEC 2.2 / SPEC.md 5.2): 401 for no/invalid/expired token, an
incomplete payload or a missing account; 403 for a disabled account; `require_*`
adds 403 on a role mismatch.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from core.errors import ApiError
from core.roles import ROLE_ADMIN, ROLE_DOCTOR, ROLE_USER
from core.security import decode_access_token
from db.session import Database
from repositories.accounts import AccountRepository, AccountRow

__all__ = [
    "ROLE_ADMIN",
    "ROLE_DOCTOR",
    "ROLE_USER",
    "CurrentUser",
    "Principal",
    "get_active_settings",
    "get_current_user",
    "get_current_user_id",
    "get_principal",
    "get_session",
    "require_admin",
    "require_authenticated",
]

AUTHORIZATION_HEADER = "Authorization"
BEARER_PREFIX = "bearer "


@dataclass(frozen=True)
class Principal:
    """The authenticated caller: an id plus one of the three roles."""

    user_id: int
    role: str


@dataclass(frozen=True)
class CurrentUser:
    """The caller plus the account row the token resolved to (FUNCTIONAL_SPEC 2.2)."""

    user_id: int
    username: str
    role: str
    row: AccountRow


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get(AUTHORIZATION_HEADER, "")
    if not header.lower().startswith(BEARER_PREFIX):
        return None
    token = header[len(BEARER_PREFIX) :].strip()
    return token or None


def get_active_settings(request: Request) -> Settings:
    return request.app.state.settings


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One session per request: commit on success, roll back on failure."""
    database: Database = request.app.state.database
    async with database.session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


def get_current_user_id(request: Request) -> int | None:
    """The owner id for endpoints that predate token auth (007-011).

    Kept as-is so this ticket does not change the already-shipped chat
    behaviour; token-backed ownership is a later concern.
    """
    return getattr(request.state, "user_id", None)


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    token = _bearer_token(request)
    if token is None:
        raise ApiError(401, "未登录")
    claims = decode_access_token(token)
    if claims is None:
        raise ApiError(401, "令牌无效或已过期")
    user_id = claims.get("user_id")
    role = claims.get("role")
    if not isinstance(user_id, int) or not isinstance(role, str):
        raise ApiError(401, "令牌数据不完整")
    try:
        row = await AccountRepository(session).find_by_id(role, user_id)
    except KeyError:
        row = None
    if row is None:
        raise ApiError(401, "用户不存在")
    if row.status == 0:
        raise ApiError(403, "账号已被禁用")
    return CurrentUser(
        user_id=user_id,
        username=str(claims.get("sub") or row.username),
        role=role,
        row=row,
    )


async def get_principal(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Principal | None:
    """The caller, or `None` for an anonymous request (no `Authorization` header)."""
    if _bearer_token(request) is None:
        return None
    user = await get_current_user(request, session)
    return Principal(user_id=user.user_id, role=user.role)


def require_authenticated(
    principal: Principal | None = Depends(get_principal),
) -> Principal:
    """401 when there is no identity at all (SPEC.md 5.4)."""
    if principal is None:
        raise ApiError(401, "未认证")
    return principal


def require_admin(principal: Principal = Depends(require_authenticated)) -> Principal:
    """403 when the caller is authenticated but not an admin (SPEC.md 5.4)."""
    if principal.role != ROLE_ADMIN:
        raise ApiError(403, "需要管理员权限")
    return principal
