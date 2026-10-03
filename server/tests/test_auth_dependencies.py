"""TICKET-012: the auth seam 011 deferred — `Authorization: Bearer` → `Principal`.

011 shipped `Principal` / `require_authenticated` (401) / `require_admin` (403)
but left `get_principal` reading `request.state`, which nothing populated. This
is the contract that ticket now fills in: the token decides the role, the role
decides the account table, and every failure mode maps to its documented status.

Observed through the admin-only `/traces` endpoint (TICKET-011), so the assertion
is on real protected HTTP, not on the dependency object.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import Settings
from core.security import create_access_token
from models.accounts import AdminRow, DoctorRow

PROTECTED = "/api/v1/traces"


async def _id_of(database_url: str, model, username: str) -> int:
    engine = create_async_engine(database_url)
    try:
        async with async_sessionmaker(engine)() as session:
            row = (
                await session.execute(select(model).where(model.username == username))
            ).scalar_one()
            return row.id
    finally:
        await engine.dispose()


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_a_real_admin_token_reaches_the_admin_only_endpoint(client, database_url):
    admin_id = await _id_of(database_url, AdminRow, "shared")
    token = create_access_token({"sub": "shared", "user_id": admin_id, "role": "admin"})

    response = await client.get(PROTECTED, headers=_bearer(token))

    assert response.status_code == 200
    assert response.json()["code"] == 200


async def test_no_token_is_401(client):
    response = await client.get(PROTECTED)

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_a_malformed_authorization_header_is_401(client):
    response = await client.get(PROTECTED, headers={"Authorization": "Token abc"})

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_a_garbage_token_is_401(client):
    response = await client.get(PROTECTED, headers=_bearer("not-a-jwt"))

    assert response.status_code == 401
    assert response.json()["message"] == "令牌无效或已过期"


async def test_an_expired_token_is_401(client, database_url):
    admin_id = await _id_of(database_url, AdminRow, "shared")
    token = create_access_token(
        {"sub": "shared", "user_id": admin_id, "role": "admin"},
        settings=Settings(jwt_expire_minutes=-1),
    )

    response = await client.get(PROTECTED, headers=_bearer(token))

    assert response.status_code == 401


async def test_an_incomplete_payload_is_401(client):
    token = create_access_token({"sub": "shared"})

    response = await client.get(PROTECTED, headers=_bearer(token))

    assert response.status_code == 401
    assert response.json()["message"] == "令牌数据不完整"


async def test_a_token_for_a_missing_account_is_401(client):
    token = create_access_token({"sub": "ghost", "user_id": 9999, "role": "admin"})

    response = await client.get(PROTECTED, headers=_bearer(token))

    assert response.status_code == 401
    assert response.json()["message"] == "用户不存在"


async def test_a_disabled_account_token_is_403(client, database_url):
    disabled_id = await _id_of(database_url, AdminRow, "admin2")
    token = create_access_token(
        {"sub": "admin2", "user_id": disabled_id, "role": "admin"}
    )

    response = await client.get(PROTECTED, headers=_bearer(token))

    assert response.status_code == 403
    assert response.json()["code"] == 403


async def test_a_doctor_token_on_an_admin_endpoint_is_403(client, database_url):
    """403 covers role mismatch: authenticated, but the wrong role (SPEC.md 5.2)."""
    doctor_id = await _id_of(database_url, DoctorRow, "shared")
    token = create_access_token(
        {"sub": "shared", "user_id": doctor_id, "role": "doctor"}
    )

    response = await client.get(PROTECTED, headers=_bearer(token))

    assert response.status_code == 403
    assert response.json()["code"] == 403
