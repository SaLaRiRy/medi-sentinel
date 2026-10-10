"""TICKET-AC-05：工单 ↔ AI 会话关联，以及医生端的 AI 上下文端点。

观察面是 C-1 契约边界：患者转人工时可以带上自己的会话；医生只能在
「可认领的工单」上看到 AI 上下文；越权、错误的关联、被删的会话都各有确定行为。
"""

import json

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models.accounts import DoctorRow, UserRow
from models.consult import ConsultMessageRow, ConsultSessionRow
from models.doctor_consult import DoctorConsultRow

PASSWORDS = {"admin": "admin-pass", "user": "user-pass", "doctor": "doctor-pass"}

GRAPH = [
    {
        "disease": "流行性感冒",
        "match_count": 2,
        "coverage": 0.67,
        "department": "呼吸内科",
        "matched_symptoms": ["发热", "头痛"],
    }
]
REFERENCES = [
    {"index": 1, "file_name": "感冒与流感指南.md", "snippet": "流感起病急……"}
]


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


async def _seed_patient(database_url: str, *, username: str) -> int:
    engine, factory = await _factory(database_url)
    try:
        async with factory() as session:
            row = UserRow(username=username, password="user-pass", real_name="李四")
            session.add(row)
            await session.commit()
            return row.id
    finally:
        await engine.dispose()


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


async def _seed_session(
    database_url: str, *, user_id: int | None, with_answer: bool = True
) -> int:
    """落一条 AI 会话；`with_answer` 决定是否带上一条含 graph/references 的助手消息。"""
    engine, factory = await _factory(database_url)
    try:
        async with factory() as session:
            consult = ConsultSessionRow(
                user_id=user_id, title="头痛三天", message_count=2 if with_answer else 1
            )
            session.add(consult)
            await session.flush()
            session.add(
                ConsultMessageRow(
                    session_id=consult.id, role="user", content="头痛三天，伴发热"
                )
            )
            if with_answer:
                session.add(
                    ConsultMessageRow(
                        session_id=consult.id,
                        role="assistant",
                        content="建议及时就医……",
                        references_json=json.dumps(REFERENCES, ensure_ascii=False),
                        graph_json=json.dumps(GRAPH, ensure_ascii=False),
                    )
                )
            await session.commit()
            return consult.id
    finally:
        await engine.dispose()


async def _stored_consult(database_url: str, consult_id: int) -> DoctorConsultRow:
    engine, factory = await _factory(database_url)
    try:
        async with factory() as session:
            row = await session.get(DoctorConsultRow, consult_id)
            assert row is not None
            return row
    finally:
        await engine.dispose()


async def _set_session_link(database_url: str, consult_id: int, session_id: int) -> None:
    """绕过接口直接改关联：用来模拟历史数据 / 不一致的关联。"""
    engine, factory = await _factory(database_url)
    try:
        async with factory() as session:
            row = await session.get(DoctorConsultRow, consult_id)
            assert row is not None
            row.session_id = session_id
            await session.commit()
    finally:
        await engine.dispose()


async def _submit(http, token: str, **overrides) -> int:
    body = {"chief_complaint": "头痛：三天，伴发热"}
    body.update(overrides)
    response = await http.post("/api/v1/consults", json=body, headers=_bearer(token))
    assert response.status_code == 200
    return response.json()["data"]["id"]


# --- 关联 ---------------------------------------------------------------------


async def test_a_patient_links_their_own_session(client, database_url):
    patient = await _token(client, role="user")
    session_id = await _seed_session(database_url, user_id=1)

    consult_id = await _submit(client, patient, session_id=session_id)

    assert (await _stored_consult(database_url, consult_id)).session_id == session_id


async def test_a_patient_cannot_link_someone_elses_session(client, database_url):
    patient = await _token(client, role="user")
    other = await _seed_patient(database_url, username="other")
    session_id = await _seed_session(database_url, user_id=other)

    response = await client.post(
        "/api/v1/consults",
        json={"chief_complaint": "头痛", "session_id": session_id},
        headers=_bearer(patient),
    )

    assert response.status_code == 404


async def test_a_missing_session_is_404(client):
    patient = await _token(client, role="user")

    response = await client.post(
        "/api/v1/consults",
        json={"chief_complaint": "头痛", "session_id": 9999},
        headers=_bearer(patient),
    )

    assert response.status_code == 404


# --- 医生端 AI 上下文 ---------------------------------------------------------


async def test_a_doctor_sees_the_ai_context_of_an_unclaimed_ticket(client, database_url):
    patient = await _token(client, role="user")
    doctor = await _token(client, role="doctor")
    session_id = await _seed_session(database_url, user_id=1)
    consult_id = await _submit(client, patient, session_id=session_id)

    response = await client.get(
        f"/api/v1/consults/{consult_id}/ai-context", headers=_bearer(doctor)
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["consult_id"] == consult_id
    assert data["session_id"] == session_id
    assert data["chief_complaint"] == "头痛：三天，伴发热"
    assert data["summary"] == "建议及时就医……"
    assert data["graph"] == GRAPH
    assert data["references"] == REFERENCES


async def test_a_ticket_without_a_session_returns_an_empty_context(client):
    patient = await _token(client, role="user")
    doctor = await _token(client, role="doctor")
    consult_id = await _submit(client, patient)

    response = await client.get(
        f"/api/v1/consults/{consult_id}/ai-context", headers=_bearer(doctor)
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["session_id"] is None
    assert data["summary"] is None
    assert data["graph"] == []
    assert data["references"] == []


async def test_a_session_without_an_answer_yields_an_empty_summary(client, database_url):
    patient = await _token(client, role="user")
    doctor = await _token(client, role="doctor")
    session_id = await _seed_session(database_url, user_id=1, with_answer=False)
    consult_id = await _submit(client, patient, session_id=session_id)

    response = await client.get(
        f"/api/v1/consults/{consult_id}/ai-context", headers=_bearer(doctor)
    )

    assert response.status_code == 200
    assert response.json()["data"]["summary"] is None


async def test_a_ticket_claimed_by_another_doctor_is_not_visible(client, database_url):
    patient = await _token(client, role="user")
    other_doctor_id = await _seed_doctor(database_url, username="doctor2")
    doctor = await _token(client, role="doctor")
    consult_id = await _submit(client, patient, doctor_id=other_doctor_id)

    response = await client.get(
        f"/api/v1/consults/{consult_id}/ai-context", headers=_bearer(doctor)
    )

    assert response.status_code == 404


async def test_the_claiming_doctor_can_still_read_it(client, database_url):
    patient = await _token(client, role="user")
    consult_id = await _submit(client, patient)
    # 先由「另一位医生」回复（顺带认领），再由他读自己的上下文。
    await _seed_doctor(database_url, username="doctor2")
    other_doctor = await _token(client, role="doctor", username="doctor2")
    await client.post(
        f"/api/v1/consults/{consult_id}/replies",
        json={"consult_id": consult_id, "content": "建议线下就诊"},
        headers=_bearer(other_doctor),
    )

    response = await client.get(
        f"/api/v1/consults/{consult_id}/ai-context", headers=_bearer(other_doctor)
    )

    assert response.status_code == 200


async def test_patients_cannot_read_the_ai_context(client):
    patient = await _token(client, role="user")
    consult_id = await _submit(client, patient)

    response = await client.get(
        f"/api/v1/consults/{consult_id}/ai-context", headers=_bearer(patient)
    )

    assert response.status_code == 403


async def test_an_unauthenticated_caller_is_401(client):
    response = await client.get("/api/v1/consults/1/ai-context")

    assert response.status_code == 401


async def test_an_unknown_ticket_is_404(client):
    doctor = await _token(client, role="doctor")

    response = await client.get(
        "/api/v1/consults/9999/ai-context", headers=_bearer(doctor)
    )

    assert response.status_code == 404


# --- 数据层防线 ---------------------------------------------------------------


async def test_a_mismatched_link_is_refused(client, database_url):
    """工单属于患者 A、会话属于患者 B：宁拒绝，也不把别人的 AI 对话交出去。"""
    patient = await _token(client, role="user")
    doctor = await _token(client, role="doctor")
    other = await _seed_patient(database_url, username="other")
    foreign_session = await _seed_session(database_url, user_id=other)
    consult_id = await _submit(client, patient)
    await _set_session_link(database_url, consult_id, foreign_session)

    response = await client.get(
        f"/api/v1/consults/{consult_id}/ai-context", headers=_bearer(doctor)
    )

    assert response.status_code == 404


async def test_a_deleted_session_yields_an_empty_context(client, database_url):
    patient = await _token(client, role="user")
    doctor = await _token(client, role="doctor")
    consult_id = await _submit(client, patient)
    await _set_session_link(database_url, consult_id, 9999)

    response = await client.get(
        f"/api/v1/consults/{consult_id}/ai-context", headers=_bearer(doctor)
    )

    assert response.status_code == 200
    assert response.json()["data"]["session_id"] is None


async def test_an_anonymous_session_is_readable(client, database_url):
    """会话没有归属（老数据）时不算越权：它不属于任何别的患者。

    这条关联只能由历史数据产生——接口层不允许患者去关联一条无归属的会话
    （那不是"他的"会话），所以这里直接改库来构造场景。
    """
    patient = await _token(client, role="user")
    doctor = await _token(client, role="doctor")
    session_id = await _seed_session(database_url, user_id=None)
    consult_id = await _submit(client, patient)
    await _set_session_link(database_url, consult_id, session_id)

    response = await client.get(
        f"/api/v1/consults/{consult_id}/ai-context", headers=_bearer(doctor)
    )

    assert response.status_code == 200
