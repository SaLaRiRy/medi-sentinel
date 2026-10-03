"""B-5: the account tables behind the three roles (TICKET-012).

Every lookup takes a `role` and only ever touches that role's table, which is
what lets one username exist in all three (FUNCTIONAL_SPEC 2.2). The session
owns the transaction; nothing here commits.
"""

from sqlalchemy import select

from core.roles import ROLE_ADMIN, ROLE_DOCTOR, ROLE_USER
from models.accounts import AdminRow, DoctorRow, UserRow
from repositories.base import Repository

AccountRow = UserRow | DoctorRow | AdminRow

_ROLE_MODELS: dict[str, type[AccountRow]] = {
    ROLE_USER: UserRow,
    ROLE_DOCTOR: DoctorRow,
    ROLE_ADMIN: AdminRow,
}


def account_model(role: str) -> type[AccountRow]:
    """The table a role reads, or `KeyError` for a role the system does not have."""
    return _ROLE_MODELS[role]


class AccountRepository(Repository):
    async def find_by_username(self, role: str, username: str) -> AccountRow | None:
        model = account_model(role)
        return (
            await self._session.execute(
                select(model).where(model.username == username)
            )
        ).scalar_one_or_none()

    async def find_by_id(self, role: str, user_id: int) -> AccountRow | None:
        model = account_model(role)
        return (
            await self._session.execute(select(model).where(model.id == user_id))
        ).scalar_one_or_none()

    async def create_user(self, **fields: object) -> UserRow:
        row = UserRow(**fields)
        self._session.add(row)
        await self._session.flush()
        return row
