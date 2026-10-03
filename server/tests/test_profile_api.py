"""TICKET-012: `/api/v1/profile/*` — the three roles' own read/write surface.

Every endpoint acts on the token's own account and takes no id, so the seam under
test is "the caller can see and edit exactly their own row". Avatar upload runs
against a temp upload dir with a tiny size cap so both 200 and 413 are reachable.
"""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

AVATAR_CAP = 32


@pytest.fixture
async def client(database_url, accounts, tmp_path):
    from core.config import Settings
    from main import create_app

    settings = Settings(
        database_url=database_url,
        upload_dir=str(tmp_path / "uploads"),
        avatar_max_bytes=AVATAR_CAP,
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as http:
            yield http


async def _token(client, *, username, password, role) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password, "role": role},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _info(client, token) -> dict:
    response = await client.get("/api/v1/profile/info", headers=_bearer(token))
    assert response.status_code == 200
    return response.json()["data"]


async def test_profile_info_requires_authentication(client):
    response = await client.get("/api/v1/profile/info")

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_patient_profile_info_exposes_patient_fields(client):
    token = await _token(client, username="shared", password="user-pass", role="user")

    data = await _info(client, token)

    assert data["role"] == "user"
    assert data["username"] == "shared"
    assert data["real_name"] == "张三"
    assert data["gender"] == 1
    assert data["status"] == 1
    assert data["avatar"] is None
    assert {"allergy_history", "age", "phone"} <= set(data)


async def test_doctor_and_admin_profile_info_expose_their_own_fields(client):
    doctor = await _info(
        client,
        await _token(client, username="shared", password="doctor-pass", role="doctor"),
    )
    admin = await _info(
        client,
        await _token(client, username="shared", password="admin-pass", role="admin"),
    )

    assert doctor["role"] == "doctor"
    assert doctor["real_name"] == "李医生"
    assert {"department_id", "title", "specialty", "introduction"} <= set(doctor)
    assert admin["role"] == "admin"
    assert admin["nickname"] == "王管理"
    assert {"email"} <= set(admin)


async def test_patient_update_writes_only_its_own_fields(client):
    token = await _token(client, username="shared", password="user-pass", role="user")

    response = await client.put(
        "/api/v1/profile/update",
        headers=_bearer(token),
        json={"real_name": "张小三", "phone": "13900000000", "nickname": "ignored"},
    )

    assert response.status_code == 200
    assert response.json()["data"] is None
    data = await _info(client, token)
    assert data["real_name"] == "张小三"
    assert data["phone"] == "13900000000"
    assert "nickname" not in data


async def test_doctor_update_writes_professional_fields(client):
    token = await _token(client, username="shared", password="doctor-pass", role="doctor")

    await client.put(
        "/api/v1/profile/update",
        headers=_bearer(token),
        json={"title": "主任医师", "specialty": "呼吸内科", "introduction": "从业 20 年"},
    )

    data = await _info(client, token)
    assert data["title"] == "主任医师"
    assert data["specialty"] == "呼吸内科"
    assert data["introduction"] == "从业 20 年"


async def test_admin_update_writes_nickname_and_email(client):
    token = await _token(client, username="shared", password="admin-pass", role="admin")

    await client.put(
        "/api/v1/profile/update",
        headers=_bearer(token),
        json={"nickname": "总管", "email": "admin@example.com"},
    )

    data = await _info(client, token)
    assert data["nickname"] == "总管"
    assert data["email"] == "admin@example.com"


async def test_password_change_swaps_the_credential(client):
    token = await _token(client, username="shared", password="user-pass", role="user")

    response = await client.put(
        "/api/v1/profile/password",
        headers=_bearer(token),
        json={"old_password": "user-pass", "new_password": "brand-new"},
    )

    assert response.status_code == 200
    relogin = await client.post(
        "/api/v1/auth/login",
        json={"username": "shared", "password": "brand-new", "role": "user"},
    )
    assert relogin.status_code == 200
    stale = await client.post(
        "/api/v1/auth/login",
        json={"username": "shared", "password": "user-pass", "role": "user"},
    )
    assert stale.status_code == 401


async def test_password_change_rejects_a_wrong_old_password_with_400(client):
    token = await _token(client, username="shared", password="user-pass", role="user")

    response = await client.put(
        "/api/v1/profile/password",
        headers=_bearer(token),
        json={"old_password": "wrong", "new_password": "brand-new"},
    )

    assert response.status_code == 400
    assert response.json()["code"] == 400


async def test_avatar_upload_stores_the_file_and_records_its_url(client, tmp_path):
    token = await _token(client, username="shared", password="user-pass", role="user")

    response = await client.post(
        "/api/v1/profile/avatar",
        headers=_bearer(token),
        files={"file": ("face.png", b"\x89PNG\x00", "image/png")},
    )

    assert response.status_code == 200
    avatar = response.json()["data"]["avatar"]
    assert avatar.startswith("/uploads33/avatar/")
    assert avatar.endswith(".png")
    stored = Path(tmp_path) / "uploads" / "avatar" / Path(avatar).name
    assert stored.read_bytes() == b"\x89PNG\x00"
    assert (await _info(client, token))["avatar"] == avatar


async def test_avatar_upload_over_the_cap_is_413(client):
    token = await _token(client, username="shared", password="user-pass", role="user")

    response = await client.post(
        "/api/v1/profile/avatar",
        headers=_bearer(token),
        files={"file": ("big.png", b"x" * (AVATAR_CAP + 1), "image/png")},
    )

    assert response.status_code == 413
    assert response.json()["code"] == 413


async def test_avatar_upload_without_a_file_is_422(client):
    token = await _token(client, username="shared", password="user-pass", role="user")

    response = await client.post("/api/v1/profile/avatar", headers=_bearer(token))

    assert response.status_code == 422
    assert response.json()["code"] == 422
