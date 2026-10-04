"""TICKET-020: `/api/v1/users` — 患者主数据（`SPEC.md` 5.4）。

管理员对患者的增删改查与状态切换；用户名重复在**本表内**返回 409
（`FUNCTIONAL_SPEC.md` 4.5）。删除患者按 `FUNCTIONAL_SPEC.md` 5.11 的顺序级联
清理：先消息后会话、先回复后工单、再预约、档案，最后患者（AC-E-08）。
"""

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models.accounts import DoctorRow, UserRow
from models.appointment import AppointmentRow
from models.consult import ConsultMessageRow, ConsultSessionRow
from models.doctor_consult import DoctorConsultRow, DoctorReplyRow
from models.health_record import HealthRecordRow

PASSWORDS = {"admin": "admin-pass", "user": "user-pass", "doctor": "doctor-pass"}


async def _token(http, *, role: str, username: str = "shared") -> str:
    response = await http.post(
        "/api/v1/auth/login",
        json={"username": username, "password": PASSWORDS[role], "role": role},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _new_engine(database_url: str):
    engine = create_async_engine(database_url)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed_user(
    database_url: str,
    *,
    username: str,
    real_name: str | None = None,
    status: int = 1,
) -> int:
    engine, factory = await _new_engine(database_url)
    try:
        async with factory() as session:
            row = UserRow(
                username=username,
                password="user-pass",
                real_name=real_name,
                status=status,
            )
            session.add(row)
            await session.commit()
            return row.id
    finally:
        await engine.dispose()


async def _stored_user(database_url: str, user_id: int):
    engine, factory = await _new_engine(database_url)
    try:
        async with factory() as session:
            return await session.get(UserRow, user_id)
    finally:
        await engine.dispose()


async def _seed_doctor_username(database_url: str, username: str) -> int:
    """Seed a doctor whose login name exists in `t_doctor` but not `t_user`."""
    engine, factory = await _new_engine(database_url)
    try:
        async with factory() as session:
            row = DoctorRow(
                username=username, password="doctor-pass", real_name="仅医生"
            )
            session.add(row)
            await session.commit()
            return row.id
    finally:
        await engine.dispose()


def _create_body(**overrides) -> dict:
    body = {
        "username": "newpatient",
        "password": "patient-pass",
        "confirm_password": "patient-pass",
        "real_name": "新患者",
        "gender": 2,
        "age": 30,
        "phone": "13800000000",
        "allergy_history": "青霉素",
    }
    body.update(overrides)
    return body


async def test_list_requires_authentication(client):
    response = await client.get("/api/v1/users")
    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_list_rejects_non_admins(client):
    token = await _token(client, role="user")

    response = await client.get("/api/v1/users", headers=_bearer(token))

    assert response.status_code == 403
    assert response.json()["code"] == 403


async def test_list_paginates_and_searches(client, database_url):
    await _seed_user(database_url, username="alice", real_name="爱丽丝")
    await _seed_user(database_url, username="bob", real_name="鲍勃")
    token = await _token(client, role="admin")

    response = await client.get(
        "/api/v1/users?page=1&page_size=10", headers=_bearer(token)
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total"] >= 3  # shared 张三 + alice + bob
    assert payload["page"] == 1
    assert payload["page_size"] == 10

    searched = await client.get(
        "/api/v1/users?page=1&page_size=10&keyword=alice", headers=_bearer(token)
    )
    items = searched.json()["data"]["items"]
    assert [item["username"] for item in items] == ["alice"]


async def test_list_rejects_out_of_range_query(client):
    token = await _token(client, role="admin")

    response = await client.get(
        "/api/v1/users?page_size=0", headers=_bearer(token)
    )

    assert response.status_code == 422
    assert response.json()["code"] == 422


async def test_create_requires_admin(client):
    response = await client.post("/api/v1/users", json=_create_body())
    assert response.status_code == 401

    token = await _token(client, role="doctor")
    response = await client.post(
        "/api/v1/users", json=_create_body(), headers=_bearer(token)
    )
    assert response.status_code == 403


async def test_create_patient(client, database_url):
    token = await _token(client, role="admin")

    response = await client.post(
        "/api/v1/users", json=_create_body(), headers=_bearer(token)
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data["id"], int)
    assert data["username"] == "newpatient"
    assert data["gender"] == 2
    assert data["status"] == 1
    row = await _stored_user(database_url, data["id"])
    assert row.password == "patient-pass"
    assert row.real_name == "新患者"
    assert row.allergy_history == "青霉素"


async def test_create_applies_gender_and_status_defaults(client, database_url):
    token = await _token(client, role="admin")

    response = await client.post(
        "/api/v1/users",
        json={
            "username": "minimal",
            "password": "patient-pass",
            "confirm_password": "patient-pass",
        },
        headers=_bearer(token),
    )

    assert response.status_code == 200
    row = await _stored_user(database_url, response.json()["data"]["id"])
    assert row.gender == 1
    assert row.status == 1


async def test_create_rejects_a_duplicate_username_with_409(client, database_url):
    await _seed_user(database_url, username="taken")
    token = await _token(client, role="admin")

    response = await client.post(
        "/api/v1/users", json=_create_body(username="taken"), headers=_bearer(token)
    )

    assert response.status_code == 409
    assert response.json()["code"] == 409


async def test_create_allows_a_username_that_exists_only_as_a_doctor(client, database_url):
    """唯一性限于本表：同一登录名可以是患者也是医生（FUNCTIONAL_SPEC 4.5）。"""
    await _seed_doctor_username(database_url, "doconly")
    token = await _token(client, role="admin")

    response = await client.post(
        "/api/v1/users", json=_create_body(username="doconly"), headers=_bearer(token)
    )

    assert response.status_code == 200


async def test_create_rejects_mismatched_passwords_with_400(client):
    token = await _token(client, role="admin")

    response = await client.post(
        "/api/v1/users",
        json=_create_body(password="patient-pass", confirm_password="other-pass"),
        headers=_bearer(token),
    )

    assert response.status_code == 400
    assert response.json()["code"] == 400


@pytest.mark.parametrize(
    "body",
    [
        {"password": "patient-pass", "confirm_password": "patient-pass"},  # 无用户名
        _create_body(username="ab"),  # 用户名过短
        _create_body(password="12345"),  # 口令过短
        {"username": "nocp", "password": "patient-pass"},  # 缺确认口令
    ],
)
async def test_create_rejects_invalid_fields_with_422(client, body):
    token = await _token(client, role="admin")

    response = await client.post(
        "/api/v1/users", json=body, headers=_bearer(token)
    )

    assert response.status_code == 422
    assert response.json()["code"] == 422


async def test_update_patient_fields(client, database_url):
    user_id = await _seed_user(database_url, username="editme", real_name="旧名")
    token = await _token(client, role="admin")

    response = await client.put(
        f"/api/v1/users/{user_id}",
        json={"real_name": "新名", "age": 40, "status": 0},
        headers=_bearer(token),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["real_name"] == "新名"
    assert data["age"] == 40
    row = await _stored_user(database_url, user_id)
    assert row.real_name == "新名"
    assert row.age == 40
    assert row.status == 0


async def test_update_patient_password_requires_a_matching_confirmation(
    client, database_url
):
    user_id = await _seed_user(database_url, username="editme")
    token = await _token(client, role="admin")

    missing = await client.put(
        f"/api/v1/users/{user_id}",
        json={"password": "brand-new"},
        headers=_bearer(token),
    )
    assert missing.status_code == 400
    assert missing.json()["code"] == 400

    mismatch = await client.put(
        f"/api/v1/users/{user_id}",
        json={"password": "brand-new", "confirm_password": "different"},
        headers=_bearer(token),
    )
    assert mismatch.status_code == 400
    assert (await _stored_user(database_url, user_id)).password == "user-pass"

    ok = await client.put(
        f"/api/v1/users/{user_id}",
        json={"password": "brand-new", "confirm_password": "brand-new"},
        headers=_bearer(token),
    )
    assert ok.status_code == 200
    assert (await _stored_user(database_url, user_id)).password == "brand-new"


async def test_update_of_a_missing_patient_is_404(client):
    token = await _token(client, role="admin")

    response = await client.put(
        "/api/v1/users/9999", json={"real_name": "X"}, headers=_bearer(token)
    )

    assert response.status_code == 404
    assert response.json()["code"] == 404


async def test_update_status(client, database_url):
    user_id = await _seed_user(database_url, username="toggleme")
    token = await _token(client, role="admin")

    response = await client.put(
        f"/api/v1/users/{user_id}/status",
        json={"status": 0},
        headers=_bearer(token),
    )

    assert response.status_code == 200
    assert (await _stored_user(database_url, user_id)).status == 0


async def test_update_status_of_a_missing_patient_is_404(client):
    token = await _token(client, role="admin")

    response = await client.put(
        "/api/v1/users/9999/status", json={"status": 1}, headers=_bearer(token)
    )

    assert response.status_code == 404
    assert response.json()["code"] == 404


async def test_delete_patient_cascades_in_order_and_spares_others(
    client, database_url
):
    target = await _seed_user(database_url, username="target")
    other = await _seed_user(database_url, username="other")

    engine, factory = await _new_engine(database_url)
    try:
        async with factory() as session:
            target_session = ConsultSessionRow(user_id=target, title="目标会话")
            other_session = ConsultSessionRow(user_id=other, title="他人会话")
            session.add_all([target_session, other_session])
            await session.flush()
            session.add_all(
                [
                    ConsultMessageRow(session_id=target_session.id, role="user", content="目标消息"),
                    ConsultMessageRow(session_id=other_session.id, role="user", content="他人消息"),
                ]
            )
            target_consult = DoctorConsultRow(
                user_id=target, doctor_id=1, chief_complaint="目标工单"
            )
            other_consult = DoctorConsultRow(
                user_id=other, doctor_id=1, chief_complaint="他人工单"
            )
            session.add_all([target_consult, other_consult])
            await session.flush()
            session.add_all(
                [
                    DoctorReplyRow(consult_id=target_consult.id, doctor_id=1, content="目标回复"),
                    DoctorReplyRow(consult_id=other_consult.id, doctor_id=1, content="他人回复"),
                ]
            )
            session.add_all(
                [
                    AppointmentRow(user_id=target, doctor_id=1, department_id=1, visit_date=date(2026, 10, 20), time_slot="上午"),
                    AppointmentRow(user_id=other, doctor_id=1, department_id=1, visit_date=date(2026, 10, 20), time_slot="上午"),
                ]
            )
            session.add_all(
                [
                    HealthRecordRow(user_id=target, doctor_id=1, record_type="门诊记录"),
                    HealthRecordRow(user_id=other, doctor_id=1, record_type="门诊记录"),
                ]
            )
            await session.commit()
            target_session_id = target_session.id
            other_session_id = other_session.id
            target_consult_id = target_consult.id
            other_consult_id = other_consult.id
    finally:
        await engine.dispose()

    token = await _token(client, role="admin")
    response = await client.delete(f"/api/v1/users/{target}", headers=_bearer(token))

    assert response.status_code == 200
    assert response.json()["data"] is None

    engine, factory = await _new_engine(database_url)
    try:
        async with factory() as session:
            assert await session.get(UserRow, target) is None
            assert await session.get(ConsultSessionRow, target_session_id) is None
            assert (
                await session.execute(
                    select(ConsultMessageRow).where(
                        ConsultMessageRow.session_id == target_session_id
                    )
                )
            ).scalars().all() == []
            assert await session.get(DoctorConsultRow, target_consult_id) is None
            assert (
                await session.execute(
                    select(DoctorReplyRow).where(
                        DoctorReplyRow.consult_id == target_consult_id
                    )
                )
            ).scalars().all() == []

            # Everything belonging to the other patient survives untouched.
            assert await session.get(UserRow, other) is not None
            assert await session.get(ConsultSessionRow, other_session_id) is not None
            assert await session.get(DoctorConsultRow, other_consult_id) is not None
            assert (
                await session.execute(
                    select(AppointmentRow).where(AppointmentRow.user_id == other)
                )
            ).scalars().all() != []
            assert (
                await session.execute(
                    select(HealthRecordRow).where(HealthRecordRow.user_id == other)
                )
            ).scalars().all() != []
            assert (
                await session.execute(
                    select(AppointmentRow).where(AppointmentRow.user_id == target)
                )
            ).scalars().all() == []
            assert (
                await session.execute(
                    select(HealthRecordRow).where(HealthRecordRow.user_id == target)
                )
            ).scalars().all() == []
    finally:
        await engine.dispose()


async def test_delete_of_a_missing_patient_is_404(client):
    token = await _token(client, role="admin")

    response = await client.delete("/api/v1/users/9999", headers=_bearer(token))

    assert response.status_code == 404
    assert response.json()["code"] == 404
