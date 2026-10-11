"""TICKET-AC-06：医生确认把工单结论沉淀为档案，并可撤回。

观察面是 C-1 契约边界 + B-5 的落库副作用：`source` / `consult_id` / `withdrawn`
三列。关键性质是「AI 建议不得直接变成病历」——只有医生的确认动作能写 `source='ai'`，
而且必须是他负责的工单。
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models.accounts import DoctorRow
from models.health_record import HealthRecordRow

PASSWORDS = {"admin": "admin-pass", "user": "user-pass", "doctor": "doctor-pass"}


async def _factory(database_url: str):
    engine = create_async_engine(database_url)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _token(http, *, role: str, username: str = "shared") -> str:
    response = await http.post(
        "/api/v1/auth/login",
        json={"username": username, "password": PASSWORDS[role], "role": role},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _seed_doctor(database_url: str, *, username: str) -> int:
    engine, factory = await _factory(database_url)
    try:
        async with factory() as session:
            row = DoctorRow(
                username=username, password="doctor-pass", real_name="王医生"
            )
            session.add(row)
            await session.commit()
            return row.id
    finally:
        await engine.dispose()


async def _rows(database_url: str) -> list[HealthRecordRow]:
    from sqlalchemy import select

    engine, factory = await _factory(database_url)
    try:
        async with factory() as session:
            result = await session.execute(
                select(HealthRecordRow).order_by(HealthRecordRow.id.asc())
            )
            return list(result.scalars().all())
    finally:
        await engine.dispose()


async def _claimed_consult(http, *, patient: str, doctor: str) -> int:
    """患者提交工单、医生回复认领，返回工单号。"""
    created = await http.post(
        "/api/v1/consults",
        json={"chief_complaint": "头痛：三天，伴发热"},
        headers=_bearer(patient),
    )
    assert created.status_code == 200
    consult_id = created.json()["data"]["id"]
    replied = await http.post(
        f"/api/v1/consults/{consult_id}/replies",
        json={"consult_id": consult_id, "content": "建议线下就诊"},
        headers=_bearer(doctor),
    )
    assert replied.status_code == 200
    return consult_id


def _body(consult_id: int, **overrides) -> dict:
    body = {"consult_id": consult_id, "record_type": "门诊记录", "diagnosis": "上感"}
    body.update(overrides)
    return body


# --- 沉淀 ---------------------------------------------------------------------


async def test_a_doctor_confirms_an_ai_suggestion_into_a_record(client, database_url):
    patient = await _token(client, role="user")
    doctor = await _token(client, role="doctor")
    consult_id = await _claimed_consult(client, patient=patient, doctor=doctor)

    response = await client.post(
        "/api/v1/records/doctor/from-consult",
        json=_body(consult_id, source="ai", treatment="多休息"),
        headers=_bearer(doctor),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["source"] == "ai"
    assert data["consult_id"] == consult_id
    assert data["user_id"] == 1

    stored = await _rows(database_url)
    assert len(stored) == 1
    assert stored[0].source == "ai"
    assert stored[0].withdrawn == 0


async def test_a_doctor_writes_his_own_conclusion_as_source_doctor(client):
    patient = await _token(client, role="user")
    doctor = await _token(client, role="doctor")
    consult_id = await _claimed_consult(client, patient=patient, doctor=doctor)

    response = await client.post(
        "/api/v1/records/doctor/from-consult",
        json=_body(consult_id),
        headers=_bearer(doctor),
    )

    assert response.status_code == 200
    assert response.json()["data"]["source"] == "doctor"


async def test_confirming_twice_is_idempotent(client, database_url):
    patient = await _token(client, role="user")
    doctor = await _token(client, role="doctor")
    consult_id = await _claimed_consult(client, patient=patient, doctor=doctor)

    first = await client.post(
        "/api/v1/records/doctor/from-consult",
        json=_body(consult_id),
        headers=_bearer(doctor),
    )
    second = await client.post(
        "/api/v1/records/doctor/from-consult",
        json=_body(consult_id, diagnosis="改过的诊断"),
        headers=_bearer(doctor),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert len(await _rows(database_url)) == 1


async def test_an_unclaimed_ticket_cannot_be_settled(client):
    patient = await _token(client, role="user")
    doctor = await _token(client, role="doctor")
    created = await client.post(
        "/api/v1/consults",
        json={"chief_complaint": "头痛"},
        headers=_bearer(patient),
    )
    consult_id = created.json()["data"]["id"]

    response = await client.post(
        "/api/v1/records/doctor/from-consult",
        json=_body(consult_id),
        headers=_bearer(doctor),
    )

    assert response.status_code == 404


async def test_a_ticket_claimed_by_another_doctor_is_404(client, database_url):
    patient = await _token(client, role="user")
    await _seed_doctor(database_url, username="doctor2")
    other = await _token(client, role="doctor", username="doctor2")
    doctor = await _token(client, role="doctor")
    consult_id = await _claimed_consult(client, patient=patient, doctor=other)

    response = await client.post(
        "/api/v1/records/doctor/from-consult",
        json=_body(consult_id),
        headers=_bearer(doctor),
    )

    assert response.status_code == 404


async def test_an_unknown_ticket_is_404(client):
    doctor = await _token(client, role="doctor")

    response = await client.post(
        "/api/v1/records/doctor/from-consult",
        json=_body(9999),
        headers=_bearer(doctor),
    )

    assert response.status_code == 404


async def test_a_patient_source_is_rejected_by_the_schema(client):
    patient = await _token(client, role="user")
    doctor = await _token(client, role="doctor")
    consult_id = await _claimed_consult(client, patient=patient, doctor=doctor)

    response = await client.post(
        "/api/v1/records/doctor/from-consult",
        json=_body(consult_id, source="patient"),
        headers=_bearer(doctor),
    )

    assert response.status_code == 422


async def test_a_patient_cannot_settle_a_ticket(client):
    patient = await _token(client, role="user")
    doctor = await _token(client, role="doctor")
    consult_id = await _claimed_consult(client, patient=patient, doctor=doctor)

    response = await client.post(
        "/api/v1/records/doctor/from-consult",
        json=_body(consult_id),
        headers=_bearer(patient),
    )

    assert response.status_code == 403


# --- 撤回与可见性 -------------------------------------------------------------


async def test_a_withdrawn_record_disappears_from_both_lists(client):
    patient = await _token(client, role="user")
    doctor = await _token(client, role="doctor")
    consult_id = await _claimed_consult(client, patient=patient, doctor=doctor)
    created = await client.post(
        "/api/v1/records/doctor/from-consult",
        json=_body(consult_id, source="ai"),
        headers=_bearer(doctor),
    )
    record_id = created.json()["data"]["id"]

    before = await client.get("/api/v1/records/my", headers=_bearer(patient))
    assert len(before.json()["data"]) == 1

    withdrawn = await client.post(
        f"/api/v1/records/doctor/{record_id}/withdraw", headers=_bearer(doctor)
    )

    assert withdrawn.status_code == 200
    after_patient = await client.get("/api/v1/records/my", headers=_bearer(patient))
    after_doctor = await client.get("/api/v1/records/doctor", headers=_bearer(doctor))
    assert after_patient.json()["data"] == []
    assert after_doctor.json()["data"] == []


async def test_a_withdrawn_record_keeps_its_row(client, database_url):
    patient = await _token(client, role="user")
    doctor = await _token(client, role="doctor")
    consult_id = await _claimed_consult(client, patient=patient, doctor=doctor)
    created = await client.post(
        "/api/v1/records/doctor/from-consult",
        json=_body(consult_id),
        headers=_bearer(doctor),
    )
    record_id = created.json()["data"]["id"]

    await client.post(
        f"/api/v1/records/doctor/{record_id}/withdraw", headers=_bearer(doctor)
    )

    stored = await _rows(database_url)
    assert len(stored) == 1
    assert stored[0].withdrawn == 1


async def test_withdrawing_twice_is_404(client):
    patient = await _token(client, role="user")
    doctor = await _token(client, role="doctor")
    consult_id = await _claimed_consult(client, patient=patient, doctor=doctor)
    created = await client.post(
        "/api/v1/records/doctor/from-consult",
        json=_body(consult_id),
        headers=_bearer(doctor),
    )
    record_id = created.json()["data"]["id"]

    first = await client.post(
        f"/api/v1/records/doctor/{record_id}/withdraw", headers=_bearer(doctor)
    )
    second = await client.post(
        f"/api/v1/records/doctor/{record_id}/withdraw", headers=_bearer(doctor)
    )

    assert first.status_code == 200
    assert second.status_code == 404


async def test_a_doctor_cannot_withdraw_someone_elses_record(client, database_url):
    patient = await _token(client, role="user")
    await _seed_doctor(database_url, username="doctor2")
    other = await _token(client, role="doctor", username="doctor2")
    doctor = await _token(client, role="doctor")
    consult_id = await _claimed_consult(client, patient=patient, doctor=other)
    created = await client.post(
        "/api/v1/records/doctor/from-consult",
        json=_body(consult_id),
        headers=_bearer(other),
    )
    record_id = created.json()["data"]["id"]

    response = await client.post(
        f"/api/v1/records/doctor/{record_id}/withdraw", headers=_bearer(doctor)
    )

    assert response.status_code == 404


async def test_the_patient_sees_where_a_record_came_from(client):
    patient = await _token(client, role="user")
    doctor = await _token(client, role="doctor")
    consult_id = await _claimed_consult(client, patient=patient, doctor=doctor)
    await client.post(
        "/api/v1/records/doctor/from-consult",
        json=_body(consult_id, source="ai"),
        headers=_bearer(doctor),
    )

    response = await client.get("/api/v1/records/my", headers=_bearer(patient))

    assert response.status_code == 200
    assert response.json()["data"][0]["source"] == "ai"
    assert response.json()["data"][0]["consult_id"] == consult_id


async def test_an_unknown_record_is_404_on_withdraw(client):
    doctor = await _token(client, role="doctor")

    response = await client.post(
        "/api/v1/records/doctor/9999/withdraw", headers=_bearer(doctor)
    )

    assert response.status_code == 404
