"""TICKET-012: `/api/v1/auth/*` — three-role login and patient self-registration.

Storage runs on a migrated SQLite database so the seam under test is the route
plus B-5; the account rows are seeded by `conftest.accounts` because
doctor/admin creation belongs to the master-data tickets (020), not this one.
"""


async def _login(client, *, username, password, role):
    return await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password, "role": role},
    )


async def test_login_returns_a_token_and_the_display_fields(client):
    response = await _login(client, username="shared", password="user-pass", role="user")

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200
    data = body["data"]
    assert set(data) == {
        "access_token",
        "token_type",
        "role",
        "user_id",
        "username",
        "display_name",
        "avatar",
    }
    assert data["token_type"] == "bearer"
    assert data["role"] == "user"
    assert data["username"] == "shared"
    assert data["display_name"] == "张三"
    assert data["avatar"] is None
    assert isinstance(data["access_token"], str) and data["access_token"]


async def test_the_same_username_resolves_to_the_table_the_role_names(client):
    """同一用户名在三张表并存，由登录时选择的角色决定查哪张表（TICKET-012）。"""
    as_user = await _login(client, username="shared", password="user-pass", role="user")
    as_doctor = await _login(
        client, username="shared", password="doctor-pass", role="doctor"
    )
    as_admin = await _login(
        client, username="shared", password="admin-pass", role="admin"
    )

    assert as_user.json()["data"]["role"] == "user"
    assert as_doctor.json()["data"]["role"] == "doctor"
    assert as_doctor.json()["data"]["display_name"] == "李医生"
    assert as_admin.json()["data"]["role"] == "admin"
    assert as_admin.json()["data"]["display_name"] == "王管理"
    # The patient password must not open the doctor account.
    assert (
        await _login(client, username="shared", password="user-pass", role="doctor")
    ).status_code == 401


async def test_login_rejects_an_unknown_role_with_400(client):
    response = await _login(client, username="shared", password="user-pass", role="ghost")

    assert response.status_code == 400
    assert response.json()["code"] == 400


async def test_login_rejects_a_wrong_password_with_401(client):
    response = await _login(client, username="shared", password="nope", role="user")

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_login_rejects_a_disabled_account_with_403(client):
    response = await _login(client, username="disabled", password="pw1234", role="user")

    assert response.status_code == 403
    assert response.json()["code"] == 403


async def test_login_rejects_a_missing_role_with_422(client):
    response = await client.post(
        "/api/v1/auth/login", json={"username": "shared", "password": "user-pass"}
    )

    assert response.status_code == 422
    assert response.json()["code"] == 422


async def test_register_creates_a_patient_and_returns_a_token(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "newcomer",
            "password": "secret1",
            "confirm_password": "secret1",
            "real_name": "新患者",
            "phone": "13800000000",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["role"] == "user"
    assert data["username"] == "newcomer"
    assert data["display_name"] == "新患者"

    # The row is really persisted: the same credentials log in afterwards.
    relogin = await _login(client, username="newcomer", password="secret1", role="user")
    assert relogin.status_code == 200


async def test_register_rejects_mismatched_passwords_with_400(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "mismatch",
            "password": "secret1",
            "confirm_password": "secret2",
        },
    )

    assert response.status_code == 400
    assert response.json()["code"] == 400


async def test_register_rejects_a_taken_username_with_409(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "shared",
            "password": "secret1",
            "confirm_password": "secret1",
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == 409


async def test_register_validates_username_and_password_length_with_422(client):
    short_username = await client.post(
        "/api/v1/auth/register",
        json={"username": "ab", "password": "secret1", "confirm_password": "secret1"},
    )
    short_password = await client.post(
        "/api/v1/auth/register",
        json={"username": "okname", "password": "12345", "confirm_password": "12345"},
    )

    assert short_username.status_code == 422
    assert short_password.status_code == 422
