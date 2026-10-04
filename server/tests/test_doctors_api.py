"""TICKET-020: `/api/v1/doctors` — 医生主数据（`SPEC.md` 5.4）。

公开列表无需认证，只显示状态为 1 且已分配科室的医生；管理员列表显示全部状态。
删除医生按 `FUNCTIONAL_SPEC.md` 5.11 的顺序级联清理，**未指派的工单保持不动**。
"""

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models.accounts import DoctorRow
from models.appointment import AppointmentRow
from models.department import DepartmentRow
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


async def _seed_department(database_url: str, *, name: str) -> int:
    engine, factory = await _new_engine(database_url)
    try:
        async with factory() as session:
            row = DepartmentRow(name=name)
            session.add(row)
            await session.commit()
            return row.id
    finally:
        await engine.dispose()


async def _seed_doctor(
    database_url: str,
    *,
    username: str,
    real_name: str,
    department_id: int | None = None,
    status: int = 1,
    title: str | None = None,
) -> int:
    engine, factory = await _new_engine(database_url)
    try:
        async with factory() as session:
            row = DoctorRow(
                username=username,
                password="doctor-pass",
                real_name=real_name,
                department_id=department_id,
                status=status,
                title=title,
            )
            session.add(row)
            await session.commit()
            return row.id
    finally:
        await engine.dispose()


async def _stored_doctor(database_url: str, doctor_id: int):
    engine, factory = await _new_engine(database_url)
    try:
        async with factory() as session:
            return await session.get(DoctorRow, doctor_id)
    finally:
        await engine.dispose()


def _create_body(**overrides) -> dict:
    body = {
        "username": "newdoctor",
        "password": "doctor-pass",
        "confirm_password": "doctor-pass",
        "real_name": "新医生",
        "title": "主任医师",
        "specialty": "心内科",
        "introduction": "从业二十年",
        "phone": "13900000000",
    }
    body.update(overrides)
    return body


async def test_public_list_needs_no_authentication(client, database_url):
    department_id = await _seed_department(database_url, name="内科")
    await _seed_doctor(
        database_url,
        username="doc1",
        real_name="李医生",
        department_id=department_id,
    )

    response = await client.get("/api/v1/doctors")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total"] == 1
    assert payload["items"][0]["real_name"] == "李医生"
    assert payload["items"][0]["department_name"] == "内科"


async def test_public_list_hides_disabled_and_unassigned_doctors(client, database_url):
    first = await _seed_department(database_url, name="内科")
    second = await _seed_department(database_url, name="外科")
    visible_a = await _seed_doctor(
        database_url, username="doc1", real_name="甲医生", department_id=first
    )
    await _seed_doctor(
        database_url, username="doc2", real_name="停用医生", department_id=first, status=0
    )
    visible_b = await _seed_doctor(
        database_url, username="doc3", real_name="乙医生", department_id=second
    )
    await _seed_doctor(database_url, username="doc4", real_name="无科室医生")

    response = await client.get("/api/v1/doctors")

    items = response.json()["data"]["items"]
    assert [item["id"] for item in items] == [visible_b, visible_a]


async def test_public_list_filters_by_department(client, database_url):
    first = await _seed_department(database_url, name="内科")
    second = await _seed_department(database_url, name="外科")
    mine = await _seed_doctor(
        database_url, username="doc1", real_name="甲医生", department_id=first
    )
    await _seed_doctor(
        database_url, username="doc2", real_name="乙医生", department_id=second
    )

    response = await client.get(f"/api/v1/doctors?department_id={first}")

    items = response.json()["data"]["items"]
    assert [item["id"] for item in items] == [mine]


async def test_public_list_searches_by_name(client, database_url):
    department_id = await _seed_department(database_url, name="内科")
    matches = await _seed_doctor(
        database_url, username="doc1", real_name="甲医生", department_id=department_id
    )
    await _seed_doctor(
        database_url, username="doc2", real_name="乙医生", department_id=department_id
    )

    response = await client.get("/api/v1/doctors?keyword=甲")

    items = response.json()["data"]["items"]
    assert [item["id"] for item in items] == [matches]


async def test_public_list_rejects_out_of_range_query(client):
    response = await client.get("/api/v1/doctors?page=0")

    assert response.status_code == 422
    assert response.json()["code"] == 422


async def test_admin_list_requires_authentication(client):
    response = await client.get("/api/v1/doctors/admin")
    assert response.status_code == 401


async def test_admin_list_rejects_non_admins(client):
    token = await _token(client, role="doctor")

    response = await client.get("/api/v1/doctors/admin", headers=_bearer(token))

    assert response.status_code == 403


async def test_admin_list_shows_every_status(client, database_url):
    department_id = await _seed_department(database_url, name="内科")
    active = await _seed_doctor(
        database_url, username="doc1", real_name="甲医生", department_id=department_id
    )
    disabled = await _seed_doctor(
        database_url,
        username="doc2",
        real_name="停用医生",
        department_id=department_id,
        status=0,
    )
    unassigned = await _seed_doctor(database_url, username="doc3", real_name="无科室医生")
    token = await _token(client, role="admin")

    response = await client.get(
        "/api/v1/doctors/admin?page=1&page_size=10", headers=_bearer(token)
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total"] == 4  # + seeded shared doctor
    assert {active, disabled, unassigned} <= {item["id"] for item in payload["items"]}


async def test_create_requires_admin(client):
    response = await client.post("/api/v1/doctors", json=_create_body())
    assert response.status_code == 401

    token = await _token(client, role="user")
    response = await client.post(
        "/api/v1/doctors", json=_create_body(), headers=_bearer(token)
    )
    assert response.status_code == 403


async def test_create_doctor(client, database_url):
    department_id = await _seed_department(database_url, name="内科")
    token = await _token(client, role="admin")

    response = await client.post(
        "/api/v1/doctors",
        json=_create_body(department_id=department_id),
        headers=_bearer(token),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["username"] == "newdoctor"
    assert data["department_id"] == department_id
    assert data["department_name"] == "内科"
    assert data["status"] == 1
    row = await _stored_doctor(database_url, data["id"])
    assert row.password == "doctor-pass"
    assert row.real_name == "新医生"


async def test_create_rejects_a_duplicate_username_with_409(client):
    token = await _token(client, role="admin")

    response = await client.post(
        "/api/v1/doctors", json=_create_body(username="shared"), headers=_bearer(token)
    )

    assert response.status_code == 409
    assert response.json()["code"] == 409


async def test_create_rejects_mismatched_passwords_with_400(client):
    token = await _token(client, role="admin")

    response = await client.post(
        "/api/v1/doctors",
        json=_create_body(password="doctor-pass", confirm_password="other-pass"),
        headers=_bearer(token),
    )

    assert response.status_code == 400


@pytest.mark.parametrize(
    "body",
    [
        {"username": "newdoctor", "password": "doctor-pass", "confirm_password": "doctor-pass"},  # 无姓名
        _create_body(username="ab"),  # 用户名过短
        _create_body(password="12345"),  # 口令过短
    ],
)
async def test_create_rejects_invalid_fields_with_422(client, body):
    token = await _token(client, role="admin")

    response = await client.post("/api/v1/doctors", json=body, headers=_bearer(token))

    assert response.status_code == 422
    assert response.json()["code"] == 422


async def test_update_doctor_fields(client, database_url):
    doctor_id = await _seed_doctor(
        database_url, username="editme", real_name="旧名", title="住院医师"
    )
    token = await _token(client, role="admin")

    response = await client.put(
        f"/api/v1/doctors/{doctor_id}",
        json={"real_name": "新名", "title": "主任医师", "status": 0},
        headers=_bearer(token),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["real_name"] == "新名"
    assert data["title"] == "主任医师"
    row = await _stored_doctor(database_url, doctor_id)
    assert row.real_name == "新名"
    assert row.status == 0


async def test_update_doctor_password_needs_a_matching_confirmation(
    client, database_url
):
    doctor_id = await _seed_doctor(database_url, username="editme", real_name="医生")
    token = await _token(client, role="admin")

    missing = await client.put(
        f"/api/v1/doctors/{doctor_id}",
        json={"password": "brand-new"},
        headers=_bearer(token),
    )
    assert missing.status_code == 400

    mismatch = await client.put(
        f"/api/v1/doctors/{doctor_id}",
        json={"password": "brand-new", "confirm_password": "different"},
        headers=_bearer(token),
    )
    assert mismatch.status_code == 400

    ok = await client.put(
        f"/api/v1/doctors/{doctor_id}",
        json={"password": "brand-new", "confirm_password": "brand-new"},
        headers=_bearer(token),
    )
    assert ok.status_code == 200
    assert (await _stored_doctor(database_url, doctor_id)).password == "brand-new"


async def test_update_of_a_missing_doctor_is_404(client):
    token = await _token(client, role="admin")

    response = await client.put(
        "/api/v1/doctors/9999", json={"real_name": "X"}, headers=_bearer(token)
    )

    assert response.status_code == 404
    assert response.json()["code"] == 404


async def test_update_status_of_a_missing_doctor_is_404(client):
    token = await _token(client, role="admin")

    response = await client.put(
        "/api/v1/doctors/9999/status", json={"status": 1}, headers=_bearer(token)
    )

    assert response.status_code == 404


async def test_update_status(client, database_url):
    doctor_id = await _seed_doctor(database_url, username="toggleme", real_name="医生")
    token = await _token(client, role="admin")

    response = await client.put(
        f"/api/v1/doctors/{doctor_id}/status",
        json={"status": 0},
        headers=_bearer(token),
    )

    assert response.status_code == 200
    assert (await _stored_doctor(database_url, doctor_id)).status == 0


async def test_delete_requires_admin(client):
    response = await client.delete("/api/v1/doctors/1")
    assert response.status_code == 401

    token = await _token(client, role="user")
    response = await client.delete("/api/v1/doctors/1", headers=_bearer(token))
    assert response.status_code == 403


async def test_delete_of_a_missing_doctor_is_404(client):
    token = await _token(client, role="admin")

    response = await client.delete("/api/v1/doctors/9999", headers=_bearer(token))

    assert response.status_code == 404


async def test_delete_doctor_cascades_and_spares_unassigned_consults(
    client, database_url
):
    doomed = await _seed_doctor(database_url, username="doomed", real_name="待删医生")
    survivor = await _seed_doctor(
        database_url, username="survivor", real_name="留存医生"
    )

    engine, factory = await _new_engine(database_url)
    try:
        async with factory() as session:
            owned_consult = DoctorConsultRow(
                user_id=1, doctor_id=doomed, chief_complaint="他的工单"
            )
            other_consult = DoctorConsultRow(
                user_id=1, doctor_id=survivor, chief_complaint="别人的工单"
            )
            unassigned = DoctorConsultRow(
                user_id=1, doctor_id=None, chief_complaint="待分配"
            )
            session.add_all([owned_consult, other_consult, unassigned])
            await session.flush()
            session.add(
                DoctorReplyRow(
                    consult_id=owned_consult.id, doctor_id=doomed, content="回复"
                )
            )
            session.add_all(
                [
                    AppointmentRow(
                        user_id=1,
                        doctor_id=doomed,
                        department_id=1,
                        visit_date=date(2026, 10, 20),
                        time_slot="上午",
                    ),
                    AppointmentRow(
                        user_id=1,
                        doctor_id=survivor,
                        department_id=1,
                        visit_date=date(2026, 10, 20),
                        time_slot="上午",
                    ),
                ]
            )
            session.add_all(
                [
                    HealthRecordRow(user_id=1, doctor_id=doomed, record_type="门诊记录"),
                    HealthRecordRow(
                        user_id=1, doctor_id=survivor, record_type="门诊记录"
                    ),
                ]
            )
            await session.commit()
            owned_consult_id = owned_consult.id
            other_consult_id = other_consult.id
            unassigned_id = unassigned.id
    finally:
        await engine.dispose()

    token = await _token(client, role="admin")
    response = await client.delete(f"/api/v1/doctors/{doomed}", headers=_bearer(token))

    assert response.status_code == 200
    assert response.json()["data"] is None

    engine, factory = await _new_engine(database_url)
    try:
        async with factory() as session:
            assert await session.get(DoctorRow, doomed) is None
            assert await session.get(DoctorConsultRow, owned_consult_id) is None
            assert (
                await session.execute(
                    select(DoctorReplyRow).where(
                        DoctorReplyRow.consult_id == owned_consult_id
                    )
                )
            ).scalars().all() == []
            assert await session.get(DoctorConsultRow, other_consult_id) is not None
            # The unassigned ticket stays exactly as it was (FUNCTIONAL_SPEC 5.11).
            kept = await session.get(DoctorConsultRow, unassigned_id)
            assert kept is not None
            assert kept.doctor_id is None
            assert (
                await session.execute(
                    select(AppointmentRow).where(AppointmentRow.doctor_id == doomed)
                )
            ).scalars().all() == []
            assert (
                await session.execute(
                    select(HealthRecordRow).where(HealthRecordRow.doctor_id == doomed)
                )
            ).scalars().all() == []
            assert (
                await session.execute(
                    select(AppointmentRow).where(AppointmentRow.doctor_id == survivor)
                )
            ).scalars().all() != []
    finally:
        await engine.dispose()
