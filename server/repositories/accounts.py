"""B-5: the account tables behind the three roles (TICKET-012 / TICKET-020).

Every lookup takes a `role` and only ever touches that role's table, which is
what lets one username exist in all three (FUNCTIONAL_SPEC 2.2). The session
owns the transaction; nothing here commits.

TICKET-020 adds the administrator's master-data operations on the same tables
(`list_page` / `create` / `update` / `set_status` / `delete`). Deleting a patient
or a doctor first runs the documented cascade (`repositories/cascade.py`), so the
ordering rule stays in one module.
"""

from sqlalchemy import func, or_, select

from core.roles import ROLE_ADMIN, ROLE_DOCTOR, ROLE_USER
from models.accounts import AdminRow, DoctorRow, UserRow
from repositories.base import Repository
from repositories.cascade import purge_doctor_scope, purge_patient_scope

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

    async def list_page(
        self,
        role: str,
        *,
        offset: int,
        limit: int,
        keyword: str | None = None,
    ) -> tuple[list[AccountRow], int]:
        """分页列出某个角色表的账号，新账号在前，可选按登录名/真名检索。"""
        model = account_model(role)
        criteria = []
        if keyword:
            pattern = f"%{keyword}%"
            matches = [model.username.like(pattern)]
            display = getattr(model, "real_name", None)
            if display is not None:
                matches.append(display.like(pattern))
            criteria.append(or_(*matches))
        total = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(model).where(*criteria)
                )
            ).scalar_one()
        )
        rows = (
            (
                await self._session.execute(
                    select(model)
                    .where(*criteria)
                    .order_by(model.id.desc())
                    .offset(offset)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), total

    async def create(self, role: str, **fields: object) -> AccountRow:
        row = account_model(role)(**fields)
        self._session.add(row)
        await self._session.flush()
        return row

    async def update(
        self, role: str, account_id: int, fields: dict
    ) -> AccountRow | None:
        """按给定字段更新；记录不存在返回 `None`（→ 404）。"""
        row = await self.find_by_id(role, account_id)
        if row is None:
            return None
        for key, value in fields.items():
            setattr(row, key, value)
        await self._session.flush()
        return row

    async def set_status(self, role: str, account_id: int, status: int) -> bool:
        """直接写入请求给定的状态值（无迁移校验，FUNCTIONAL_SPEC 5.10）。"""
        row = await self.find_by_id(role, account_id)
        if row is None:
            return False
        row.status = status
        return True

    async def delete(self, role: str, account_id: int) -> bool:
        """删除账号：患者/医生先按 5.11 的顺序清理关联业务数据。"""
        row = await self.find_by_id(role, account_id)
        if row is None:
            return False
        if role == ROLE_USER:
            await purge_patient_scope(self._session, account_id)
        elif role == ROLE_DOCTOR:
            await purge_doctor_scope(self._session, account_id)
        await self._session.delete(row)
        return True
