"""TICKET-017: `/api/v1/appointments` — 预约挂号（`SPEC.md` 5.4「预约与健康档案」）。

本票的观察面是 C-1 契约边界：对真实应用发 HTTP 请求，断言的是「患者提交后
读得回来、医生只看得到自己的排期、管理员可过滤、状态更新与删除的存在性语义」。
数据库只作为副作用核对点，不当作接口使用（B-5 的交易边界由 `get_session` 覆盖）。
"""

from datetime import date

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models.accounts import DoctorRow
from models.appointment import (
    APPOINTMENT_STATUS_CANCELLED,
    APPOINTMENT_STATUS_COMPLETED,
    APPOINTMENT_STATUS_CONFIRMED,
    APPOINTMENT_STATUS_PENDING,
    AppointmentRow,
)

PASSWORDS = {"admin": "admin-pass", "user": "user-pass", "doctor": "doctor-pass"}


async def _token(http, *, role: str) -> str:
    response = await http.post(
        "/api/v1/auth/login",
        json={"username": "shared", "password": PASSWORDS[role], "role": role},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _payload(**overrides) -> dict:
    body = {
        "doctor_id": 1,
        "department_id": 1,
        "visit_date": "2026-10-20",
        "time_slot": "上午",
    }
    body.update(overrides)
    return body


async def _stored(database_url: str, appointment_id: int) -> AppointmentRow | None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            return await session.get(AppointmentRow, appointment_id)
    finally:
        await engine.dispose()


async def _seed_doctor(
    database_url: str, *, username: str, password: str, real_name: str
) -> int:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            row = DoctorRow(username=username, password=password, real_name=real_name)
            session.add(row)
            await session.commit()
            return row.id
    finally:
        await engine.dispose()


async def _seed_appointment(
    database_url: str,
    *,
    user_id: int = 1,
    doctor_id: int = 1,
    department_id: int,
    visit_date: date,
    time_slot: str = "上午",
    status: int = APPOINTMENT_STATUS_PENDING,
    remark: str | None = None,
) -> int:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            row = AppointmentRow(
                user_id=user_id,
                doctor_id=doctor_id,
                department_id=department_id,
                visit_date=visit_date,
                time_slot=time_slot,
                status=status,
                remark=remark,
            )
            session.add(row)
            await session.commit()
            return row.id
    finally:
        await engine.dispose()


async def test_create_requires_authentication(client):
    response = await client.post("/api/v1/appointments", json=_payload())

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_create_is_for_patients_only(client):
    token = await _token(client, role="doctor")

    response = await client.post(
        "/api/v1/appointments", json=_payload(), headers=_bearer(token)
    )

    assert response.status_code == 403
    assert response.json()["code"] == 403


async def test_patient_submits_an_appointment_and_it_lands_as_pending(
    client, database_url
):
    token = await _token(client, role="user")

    response = await client.post(
        "/api/v1/appointments",
        json=_payload(time_slot="下午", remark="复诊"),
        headers=_bearer(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200
    assert isinstance(body["data"]["id"], int)

    row = await _stored(database_url, body["data"]["id"])
    assert row is not None
    assert row.user_id == 1
    assert row.doctor_id == 1
    assert row.department_id == 1
    assert str(row.visit_date) == "2026-10-20"
    assert row.time_slot == "下午"
    assert row.remark == "复诊"
    assert row.status == APPOINTMENT_STATUS_PENDING


@pytest.mark.parametrize(
    "missing", ["doctor_id", "department_id", "visit_date", "time_slot"]
)
async def test_create_rejects_a_missing_required_field(client, missing):
    token = await _token(client, role="user")
    body = _payload()
    body.pop(missing)

    response = await client.post(
        "/api/v1/appointments", json=body, headers=_bearer(token)
    )

    assert response.status_code == 422
    assert response.json()["code"] == 422


async def _create(http, token: str, **overrides) -> int:
    response = await http.post(
        "/api/v1/appointments", json=_payload(**overrides), headers=_bearer(token)
    )
    assert response.status_code == 200
    return response.json()["data"]["id"]


async def _register_second_patient(http) -> str:
    response = await http.post(
        "/api/v1/auth/register",
        json={
            "username": "other",
            "password": "other-pass",
            "confirm_password": "other-pass",
            "real_name": "李四",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


async def test_my_appointments_requires_authentication(client):
    response = await client.get("/api/v1/appointments/my")

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_my_appointments_is_for_patients_only(client):
    token = await _token(client, role="doctor")

    response = await client.get("/api/v1/appointments/my", headers=_bearer(token))

    assert response.status_code == 403
    assert response.json()["code"] == 403


async def test_my_appointments_returns_only_the_callers_rows(client):
    token = await _token(client, role="user")
    first = await _create(client, token, visit_date="2026-10-20", remark="复诊")
    second = await _create(client, token, visit_date="2026-10-21", time_slot="晚上")
    other = await _register_second_patient(client)
    await _create(client, other, visit_date="2026-10-22")

    response = await client.get("/api/v1/appointments/my", headers=_bearer(token))

    assert response.status_code == 200
    items = response.json()["data"]
    assert {item["id"] for item in items} == {first, second}
    mine = next(item for item in items if item["id"] == first)
    assert mine["user_id"] == 1
    assert mine["doctor_id"] == 1
    assert mine["department_id"] == 1
    assert mine["visit_date"] == "2026-10-20"
    assert mine["time_slot"] == "上午"
    assert mine["status"] == APPOINTMENT_STATUS_PENDING
    assert mine["remark"] == "复诊"


async def test_my_appointments_is_empty_for_a_patient_without_any(client):
    token = await _register_second_patient(client)

    response = await client.get("/api/v1/appointments/my", headers=_bearer(token))

    assert response.status_code == 200
    assert response.json()["data"] == []


async def test_doctor_schedule_requires_authentication(client):
    response = await client.get("/api/v1/appointments/doctor")

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_doctor_schedule_is_for_doctors_only(client):
    token = await _token(client, role="user")

    response = await client.get(
        "/api/v1/appointments/doctor", headers=_bearer(token)
    )

    assert response.status_code == 403
    assert response.json()["code"] == 403


async def test_doctor_schedule_returns_only_that_doctors_rows(client, database_url):
    other_doctor_id = await _seed_doctor(
        database_url, username="doc2", password="doc2-pass", real_name="王医生"
    )
    patient = await _token(client, role="user")
    mine = await _create(client, patient, doctor_id=1, remark="我的排期")
    await _create(client, patient, doctor_id=other_doctor_id)

    token = await _token(client, role="doctor")
    response = await client.get(
        "/api/v1/appointments/doctor", headers=_bearer(token)
    )

    assert response.status_code == 200
    items = response.json()["data"]
    assert [item["id"] for item in items] == [mine]
    assert items[0]["doctor_id"] == 1
    assert items[0]["doctor_name"] == "李医生"
    assert items[0]["user_name"] == "张三"


def _admin_query(**overrides) -> str:
    params = {"page": 1, "page_size": 10}
    params.update({key: value for key, value in overrides.items() if value is not None})
    return "?" + "&".join(f"{key}={value}" for key, value in params.items())


async def _admin_list(http, token: str, query: str = ""):
    return await http.get(f"/api/v1/appointments/admin{query}", headers=_bearer(token))


async def test_admin_list_requires_authentication(client):
    response = await client.get("/api/v1/appointments/admin")

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_admin_list_rejects_non_admins(client):
    token = await _token(client, role="user")

    response = await _admin_list(client, token)

    assert response.status_code == 403
    assert response.json()["code"] == 403


async def test_admin_list_paginates_and_filters(client, database_url):
    keep = await _seed_appointment(
        database_url, department_id=1, visit_date=date(2026, 10, 20), remark="复诊"
    )
    await _seed_appointment(
        database_url,
        department_id=1,
        visit_date=date(2026, 10, 21),
        status=APPOINTMENT_STATUS_CONFIRMED,
    )
    await _seed_appointment(
        database_url,
        department_id=2,
        visit_date=date(2026, 10, 20),
        status=APPOINTMENT_STATUS_PENDING,
    )
    third = await _seed_appointment(
        database_url,
        department_id=2,
        visit_date=date(2026, 10, 20),
        status=APPOINTMENT_STATUS_CANCELLED,
    )
    await _seed_appointment(
        database_url,
        department_id=3,
        visit_date=date(2026, 10, 22),
        status=APPOINTMENT_STATUS_COMPLETED,
    )
    token = await _token(client, role="admin")

    first = (await _admin_list(client, token, _admin_query(page_size=2))).json()
    assert first["data"]["total"] == 5
    assert first["data"]["page"] == 1
    assert first["data"]["page_size"] == 2
    assert len(first["data"]["items"]) == 2
    assert set(first["data"]["items"][0]) >= {
        "id",
        "user_id",
        "user_name",
        "doctor_id",
        "doctor_name",
        "department_id",
        "visit_date",
        "time_slot",
        "status",
    }
    second = (await _admin_list(client, token, _admin_query(page=2, page_size=2))).json()
    last = (await _admin_list(client, token, _admin_query(page=3, page_size=2))).json()
    assert len(second["data"]["items"]) == 2
    assert len(last["data"]["items"]) == 1

    by_department = (
        await _admin_list(client, token, _admin_query(department_id=1))
    ).json()
    assert by_department["data"]["total"] == 2

    by_date = (await _admin_list(client, token, _admin_query(visit_date="2026-10-20"))).json()
    assert by_date["data"]["total"] == 3

    by_status = (
        await _admin_list(client, token, _admin_query(status=APPOINTMENT_STATUS_PENDING))
    ).json()
    assert by_status["data"]["total"] == 2

    combined = (
        await _admin_list(
            client,
            token,
            _admin_query(
                department_id=2, status=APPOINTMENT_STATUS_CANCELLED
            ),
        )
    ).json()
    assert [item["id"] for item in combined["data"]["items"]] == [third]

    by_remark = (await _admin_list(client, token, _admin_query(keyword="复诊"))).json()
    assert [item["id"] for item in by_remark["data"]["items"]] == [keep]

    by_patient = (await _admin_list(client, token, _admin_query(keyword="张三"))).json()
    assert by_patient["data"]["total"] == 5


async def test_admin_list_rejects_out_of_range_query(client):
    token = await _token(client, role="admin")

    response = await _admin_list(client, token, _admin_query(page=0))

    assert response.status_code == 422
    assert response.json()["code"] == 422


async def _set_status(http, token: str, appointment_id: int, body):
    return await http.put(
        f"/api/v1/appointments/{appointment_id}/status",
        json=body,
        headers=_bearer(token),
    )


async def test_status_update_requires_authentication(client):
    response = await client.put(
        "/api/v1/appointments/1/status", json={"status": 1}
    )

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_status_update_is_for_doctors_and_admins_only(client):
    token = await _token(client, role="user")

    response = await _set_status(client, token, 1, {"status": 1})

    assert response.status_code == 403
    assert response.json()["code"] == 403


async def test_admin_updates_the_status(client, database_url):
    appointment_id = await _seed_appointment(
        database_url, department_id=1, visit_date=date(2026, 10, 20)
    )
    token = await _token(client, role="admin")

    response = await _set_status(
        client, token, appointment_id, {"status": APPOINTMENT_STATUS_COMPLETED}
    )

    assert response.status_code == 200
    assert response.json()["data"] is None
    row = await _stored(database_url, appointment_id)
    assert row.status == APPOINTMENT_STATUS_COMPLETED


async def test_doctor_updates_the_status(client, database_url):
    appointment_id = await _seed_appointment(
        database_url,
        department_id=1,
        visit_date=date(2026, 10, 20),
        status=APPOINTMENT_STATUS_PENDING,
    )
    token = await _token(client, role="doctor")

    response = await _set_status(
        client, token, appointment_id, {"status": APPOINTMENT_STATUS_CONFIRMED}
    )

    assert response.status_code == 200
    row = await _stored(database_url, appointment_id)
    assert row.status == APPOINTMENT_STATUS_CONFIRMED


async def test_status_update_writes_an_undefined_value_verbatim(
    client, database_url
):
    """SPEC.md 7.3：状态迁移校验不在范围内，请求给什么值就写什么值。"""
    appointment_id = await _seed_appointment(
        database_url, department_id=1, visit_date=date(2026, 10, 20)
    )
    token = await _token(client, role="admin")

    response = await _set_status(client, token, appointment_id, {"status": 9})

    assert response.status_code == 200
    row = await _stored(database_url, appointment_id)
    assert row.status == 9


async def test_status_update_of_a_missing_appointment_is_404(client):
    for role in ("admin", "doctor"):
        token = await _token(client, role=role)

        response = await _set_status(client, token, 9999, {"status": 1})

        assert response.status_code == 404
        assert response.json()["code"] == 404


async def test_status_update_rejects_a_malformed_body(client, database_url):
    appointment_id = await _seed_appointment(
        database_url, department_id=1, visit_date=date(2026, 10, 20)
    )
    token = await _token(client, role="admin")

    response = await _set_status(client, token, appointment_id, {})

    assert response.status_code == 422
    assert response.json()["code"] == 422


async def _delete(http, token: str, appointment_id: int):
    return await http.delete(
        f"/api/v1/appointments/admin/{appointment_id}", headers=_bearer(token)
    )


async def test_delete_requires_authentication(client):
    response = await client.delete("/api/v1/appointments/admin/1")

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_delete_is_for_admins_only(client):
    for role in ("user", "doctor"):
        token = await _token(client, role=role)

        response = await _delete(client, token, 1)

        assert response.status_code == 403
        assert response.json()["code"] == 403


async def test_admin_deletes_the_appointment(client, database_url):
    appointment_id = await _seed_appointment(
        database_url, department_id=1, visit_date=date(2026, 10, 20)
    )
    token = await _token(client, role="admin")

    response = await _delete(client, token, appointment_id)

    assert response.status_code == 200
    assert response.json()["data"] is None
    assert await _stored(database_url, appointment_id) is None


async def test_delete_of_a_missing_appointment_is_404(client):
    token = await _token(client, role="admin")

    response = await _delete(client, token, 9999)

    assert response.status_code == 404
    assert response.json()["code"] == 404
