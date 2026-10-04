"""TICKET-018: `/api/v1/records` — 健康档案（`SPEC.md` 5.4「预约与健康档案」）。

本票的观察面是 C-1 契约边界：对真实应用发 HTTP 请求，断言的是「医生为患者
建档后读得回来、患者只看得到本人档案、医生只看得到自己名下的档案」。数据库只
作为副作用核对点，不当作接口使用（B-5 的交易边界由 `get_session` 覆盖）。
"""

from datetime import date

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models.accounts import DoctorRow
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


def _payload(**overrides) -> dict:
    body = {"user_id": 1, "record_type": "门诊记录"}
    body.update(overrides)
    return body


async def _stored(database_url: str, record_id: int) -> HealthRecordRow | None:
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            return await session.get(HealthRecordRow, record_id)
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


async def test_create_requires_authentication(client):
    response = await client.post("/api/v1/records/doctor", json=_payload())

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_create_is_for_doctors_only(client):
    token = await _token(client, role="user")

    response = await client.post(
        "/api/v1/records/doctor", json=_payload(), headers=_bearer(token)
    )

    assert response.status_code == 403
    assert response.json()["code"] == 403


async def test_doctor_creates_a_record_for_a_patient_and_it_lands(
    client, database_url
):
    token = await _token(client, role="doctor")

    response = await client.post(
        "/api/v1/records/doctor",
        json=_payload(
            record_type="住院记录",
            diagnosis="急性阑尾炎",
            treatment="手术切除",
            prescription="头孢呋辛",
            visit_date="2026-10-20",
        ),
        headers=_bearer(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200
    record = body["data"]
    assert isinstance(record["id"], int)
    assert record["user_id"] == 1
    assert record["user_name"] == "张三"
    assert record["doctor_id"] == 1
    assert record["doctor_name"] == "李医生"
    assert record["record_type"] == "住院记录"
    assert record["diagnosis"] == "急性阑尾炎"
    assert record["treatment"] == "手术切除"
    assert record["prescription"] == "头孢呋辛"
    assert record["visit_date"] == "2026-10-20"
    assert record["create_time"] is not None

    row = await _stored(database_url, record["id"])
    assert row is not None
    assert row.user_id == 1
    assert row.doctor_id == 1
    assert row.record_type == "住院记录"
    assert row.diagnosis == "急性阑尾炎"
    assert row.treatment == "手术切除"
    assert row.prescription == "头孢呋辛"
    assert row.visit_date == date(2026, 10, 20)


async def test_my_records_requires_authentication(client):
    response = await client.get("/api/v1/records/my")

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_my_records_is_for_patients_only(client):
    token = await _token(client, role="doctor")

    response = await client.get("/api/v1/records/my", headers=_bearer(token))

    assert response.status_code == 403
    assert response.json()["code"] == 403


async def test_my_records_returns_only_the_callers_rows(client, database_url):
    doctor = await _token(client, role="doctor")
    first = (
        await client.post(
            "/api/v1/records/doctor",
            json=_payload(record_type="门诊记录"),
            headers=_bearer(doctor),
        )
    ).json()["data"]["id"]
    other = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "other",
            "password": "other-pass",
            "confirm_password": "other-pass",
            "real_name": "李四",
        },
    )
    other_id = other.json()["data"]["user_id"]
    await client.post(
        "/api/v1/records/doctor",
        json=_payload(user_id=other_id, record_type="体检报告"),
        headers=_bearer(doctor),
    )

    patient = await _token(client, role="user")
    response = await client.get("/api/v1/records/my", headers=_bearer(patient))

    assert response.status_code == 200
    items = response.json()["data"]
    assert [item["id"] for item in items] == [first]
    assert items[0]["user_id"] == 1
    assert items[0]["record_type"] == "门诊记录"


async def test_doctor_records_returns_only_that_doctors_rows(client, database_url):
    other_doctor_id = await _seed_doctor(
        database_url, username="doc2", password="doctor-pass", real_name="王医生"
    )
    token = await _token(client, role="doctor")
    mine = (
        await client.post(
            "/api/v1/records/doctor", json=_payload(), headers=_bearer(token)
        )
    ).json()["data"]["id"]
    other_doctor = await _token(client, role="doctor", username="doc2")
    await client.post(
        "/api/v1/records/doctor", json=_payload(), headers=_bearer(other_doctor)
    )

    response = await client.get("/api/v1/records/doctor", headers=_bearer(token))

    assert response.status_code == 200
    items = response.json()["data"]
    assert [item["id"] for item in items] == [mine]
    assert items[0]["doctor_id"] == 1
    assert other_doctor_id != 1


async def test_create_with_an_unknown_patient_is_404(client):
    token = await _token(client, role="doctor")

    response = await client.post(
        "/api/v1/records/doctor",
        json=_payload(user_id=9999),
        headers=_bearer(token),
    )

    assert response.status_code == 404
    assert response.json()["code"] == 404


@pytest.mark.parametrize(
    "body",
    [
        {"user_id": 1},
        {"user_id": 1, "record_type": ""},
        {"user_id": 1, "record_type": "x" * 51},
        {"user_id": 1, "record_type": "门诊记录", "diagnosis": "x" * 256},
    ],
)
async def test_create_rejects_invalid_fields_with_422(client, body):
    token = await _token(client, role="doctor")

    response = await client.post(
        "/api/v1/records/doctor", json=body, headers=_bearer(token)
    )

    assert response.status_code == 422
    assert response.json()["code"] == 422


async def _create(http, token: str, **overrides) -> int:
    response = await http.post(
        "/api/v1/records/doctor", json=_payload(**overrides), headers=_bearer(token)
    )
    assert response.status_code == 200
    return response.json()["data"]["id"]


async def _update(http, token: str, record_id: int, body: dict):
    return await http.put(
        f"/api/v1/records/doctor/{record_id}", json=body, headers=_bearer(token)
    )


async def _delete(http, token: str, record_id: int):
    return await http.delete(
        f"/api/v1/records/doctor/{record_id}", headers=_bearer(token)
    )


async def test_update_requires_authentication(client):
    response = await client.put("/api/v1/records/doctor/1", json={"record_type": "x"})

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_update_is_for_doctors_only(client):
    token = await _token(client, role="user")

    response = await _update(client, token, 1, {"record_type": "复诊记录"})

    assert response.status_code == 403
    assert response.json()["code"] == 403


async def test_update_writes_the_new_fields(client, database_url):
    token = await _token(client, role="doctor")
    record_id = await _create(client, token, record_type="门诊记录")

    response = await _update(
        client,
        token,
        record_id,
        {"record_type": "复诊记录", "diagnosis": "已好转", "visit_date": "2026-11-01"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == record_id
    assert data["record_type"] == "复诊记录"
    assert data["diagnosis"] == "已好转"
    assert data["visit_date"] == "2026-11-01"

    row = await _stored(database_url, record_id)
    assert row.record_type == "复诊记录"
    assert row.diagnosis == "已好转"
    assert row.visit_date == date(2026, 11, 1)


async def test_update_of_a_missing_record_is_404(client):
    token = await _token(client, role="doctor")

    response = await _update(client, token, 9999, {"record_type": "复诊记录"})

    assert response.status_code == 404
    assert response.json()["code"] == 404


async def test_update_of_another_doctors_record_is_404_and_changes_nothing(
    client, database_url
):
    await _seed_doctor(
        database_url, username="doc2", password="doctor-pass", real_name="王医生"
    )
    other_doctor = await _token(client, role="doctor", username="doc2")
    record_id = await _create(
        client, other_doctor, record_type="住院记录", diagnosis="原始诊断"
    )

    mine = await _token(client, role="doctor")
    response = await _update(
        client, mine, record_id, {"record_type": "篡改", "diagnosis": "篡改"}
    )

    assert response.status_code == 404
    assert response.json()["code"] == 404
    row = await _stored(database_url, record_id)
    assert row.record_type == "住院记录"
    assert row.diagnosis == "原始诊断"
    assert row.doctor_id == 2


async def test_delete_requires_authentication(client):
    response = await client.delete("/api/v1/records/doctor/1")

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_delete_is_for_doctors_only(client):
    token = await _token(client, role="user")

    response = await _delete(client, token, 1)

    assert response.status_code == 403
    assert response.json()["code"] == 403


async def test_doctor_deletes_own_record(client, database_url):
    token = await _token(client, role="doctor")
    record_id = await _create(client, token)

    response = await _delete(client, token, record_id)

    assert response.status_code == 200
    assert response.json()["data"] is None
    assert await _stored(database_url, record_id) is None


async def test_delete_of_a_missing_record_is_404(client):
    token = await _token(client, role="doctor")

    response = await _delete(client, token, 9999)

    assert response.status_code == 404
    assert response.json()["code"] == 404


async def test_delete_of_another_doctors_record_is_404_and_keeps_it(
    client, database_url
):
    await _seed_doctor(
        database_url, username="doc2", password="doctor-pass", real_name="王医生"
    )
    other_doctor = await _token(client, role="doctor", username="doc2")
    record_id = await _create(client, other_doctor)

    mine = await _token(client, role="doctor")
    response = await _delete(client, mine, record_id)

    assert response.status_code == 404
    assert response.json()["code"] == 404
    assert await _stored(database_url, record_id) is not None


async def _register_patient(http, username: str, real_name: str) -> tuple[int, str]:
    response = await http.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "password": "patient-pass",
            "confirm_password": "patient-pass",
            "real_name": real_name,
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    return data["user_id"], data["access_token"]


async def _book(http, patient_token: str, *, doctor_id: int = 1) -> int:
    response = await http.post(
        "/api/v1/appointments",
        json={
            "doctor_id": doctor_id,
            "department_id": 1,
            "visit_date": "2026-10-20",
            "time_slot": "上午",
        },
        headers=_bearer(patient_token),
    )
    assert response.status_code == 200
    return response.json()["data"]["id"]


async def test_patient_options_requires_authentication(client):
    response = await client.get("/api/v1/records/doctor/patient-options")

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_patient_options_is_for_doctors_only(client):
    token = await _token(client, role="user")

    response = await client.get(
        "/api/v1/records/doctor/patient-options", headers=_bearer(token)
    )

    assert response.status_code == 403
    assert response.json()["code"] == 403


async def test_patient_options_is_the_deduplicated_union_of_appointments_and_records(
    client,
):
    patient = await _token(client, role="user")  # user_id 1 张三
    other_id, other_token = await _register_patient(client, "other", "李四")
    third_id, _ = await _register_patient(client, "third", "王五")
    doctor = await _token(client, role="doctor")

    await _book(client, patient)  # 预约人：张三
    await _book(client, other_token)  # 预约人：李四
    await _create(client, doctor, user_id=1)  # 已建档人：张三（去重）
    await _create(client, doctor, user_id=third_id)  # 已建档人：王五

    response = await client.get(
        "/api/v1/records/doctor/patient-options", headers=_bearer(doctor)
    )

    assert response.status_code == 200
    options = response.json()["data"]
    assert options == [
        {"id": 1, "name": "张三"},
        {"id": other_id, "name": "李四"},
        {"id": third_id, "name": "王五"},
    ]


async def test_patient_options_is_empty_for_a_doctor_without_patients(
    client, database_url
):
    await _seed_doctor(
        database_url, username="doc2", password="doctor-pass", real_name="王医生"
    )
    token = await _token(client, role="doctor", username="doc2")

    response = await client.get(
        "/api/v1/records/doctor/patient-options", headers=_bearer(token)
    )

    assert response.status_code == 200
    assert response.json()["data"] == []


async def _submit_consult(http, token: str, doctor_id: int | None) -> int:
    response = await http.post(
        "/api/v1/consults",
        json={"doctor_id": doctor_id, "chief_complaint": "头痛：三天"},
        headers=_bearer(token),
    )
    assert response.status_code == 200
    return response.json()["data"]["id"]


async def test_patient_options_also_covers_the_doctors_consults(client):
    """TICKET-018 挂账第 1 条（本票承接）：问诊人并入可选患者。"""
    patient = await _token(client, role="user")  # user_id 1 张三
    other_id, other_token = await _register_patient(client, "other", "李四")
    third_id, third_token = await _register_patient(client, "third", "王五")
    doctor = await _token(client, role="doctor")

    await _submit_consult(client, patient, doctor_id=1)
    await _submit_consult(client, other_token, doctor_id=1)
    await _submit_consult(client, third_token, doctor_id=None)  # 待分配，不算任何医生的问诊人

    response = await client.get(
        "/api/v1/records/doctor/patient-options", headers=_bearer(doctor)
    )

    assert response.status_code == 200
    options = response.json()["data"]
    assert options == [
        {"id": 1, "name": "张三"},
        {"id": other_id, "name": "李四"},
    ]
    assert third_id not in {option["id"] for option in options}


def test_the_record_endpoints_are_published_in_the_contract(database_url):
    from core.config import Settings
    from main import create_app

    paths = create_app(Settings(database_url=database_url)).openapi()["paths"]

    assert "/api/v1/records/my" in paths
    assert "/api/v1/records/doctor" in paths
    assert "/api/v1/records/doctor/patient-options" in paths
    assert "/api/v1/records/doctor/{record_id}" in paths


def test_the_record_endpoints_declare_their_spec_error_branches(database_url):
    """AC-B-41：契约声明的错误分支与 SPEC.md 5.4 一致。"""
    from core.config import Settings
    from main import create_app

    paths = create_app(Settings(database_url=database_url)).openapi()["paths"]

    def declared(path: str, method: str) -> set[str]:
        return set(paths[path][method]["responses"])

    assert declared("/api/v1/records/my", "get") >= {"200", "401", "403"}
    assert declared("/api/v1/records/doctor", "get") >= {"200", "401", "403"}
    assert declared("/api/v1/records/doctor/patient-options", "get") >= {
        "200",
        "401",
        "403",
    }
    assert declared("/api/v1/records/doctor", "post") >= {
        "200",
        "401",
        "403",
        "404",
        "422",
    }
    assert declared("/api/v1/records/doctor/{record_id}", "put") >= {
        "200",
        "401",
        "403",
        "404",
        "422",
    }
    assert declared("/api/v1/records/doctor/{record_id}", "delete") >= {
        "200",
        "401",
        "403",
        "404",
    }
