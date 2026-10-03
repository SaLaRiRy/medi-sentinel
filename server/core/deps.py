"""FastAPI dependencies that expose the B-5 session and the running settings."""

from collections.abc import AsyncIterator
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from core.errors import ApiError
from db.session import Database

# The three roles of the token model (SPEC.md 3.6 / FUNCTIONAL_SPEC 附录 A).
ROLE_USER = "user"
ROLE_DOCTOR = "doctor"
ROLE_ADMIN = "admin"


@dataclass(frozen=True)
class Principal:
    """The authenticated caller: an id plus one of the three roles.

    Token auth (TICKET-012) is what will populate `request.state.user_id` /
    `request.state.role`; the observability endpoints read it through this one
    seam, so tightening the token layer later does not touch them.
    """

    user_id: int
    role: str


def get_active_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_current_user_id(request: Request) -> int | None:
    """The authenticated patient's id for the endpoints that need an owner.

    Token auth arrives with TICKET-012; until then a middleware may set
    `request.state.user_id`, and otherwise the consult is stored without an
    owner rather than with a fabricated one.
    """
    return getattr(request.state, "user_id", None)


def get_principal(request: Request) -> Principal | None:
    """The caller if both an id and a role are present, else `None` (unauthenticated)."""
    user_id = getattr(request.state, "user_id", None)
    role = getattr(request.state, "role", None)
    if user_id is None or role is None:
        return None
    return Principal(user_id=int(user_id), role=str(role))


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
