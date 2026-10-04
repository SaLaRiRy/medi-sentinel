"""TICKET-019: `/api/v1/consults` — 人工问诊工单（`SPEC.md` 5.4「人工问诊」）。

本票的观察面是 C-1 契约边界：对真实应用发 HTTP 请求，断言的是「患者提交后
读得回来、医生只看得到可认领的工单并先到先得、管理员可过滤与删除」。数据库只
作为副作用核对点（B-5 的交易边界由 `get_session` 覆盖）。
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models.accounts import DoctorRow, UserRow
from models.doctor_consult import (
    CONSULT_STATUS_PENDING,
    CONSULT_STATUS_REPLIED,
    DoctorConsultRow,
    DoctorReplyRow,
)

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


async def _stored_consult(
    database_url: str, consult_id: int
) -> DoctorConsultRow | None:
    engine, factory = await _new_engine(database_url)
    try:
        async with factory() as session:
            return await session.get(DoctorConsultRow, consult_id)
    finally:
        await engine.dispose()


async def _stored_replies(database_url: str, consult_id: int) -> list[DoctorReplyRow]:
    from sqlalchemy import select

    engine, factory = await _new_engine(database_url)
    try:
        async with factory() as session:
            rows = (
                (
                    await session.execute(
                        select(DoctorReplyRow)
                        .where(DoctorReplyRow.consult_id == consult_id)
                        .order_by(DoctorReplyRow.id.asc())
                    )
                )
                .scalars()
                .all()
            )
            return list(rows)
    finally:
        await engine.dispose()


async def _seed_doctor(
    database_url: str, *, username: str, password: str, real_name: str
) -> int:
    engine, factory = await _new_engine(database_url)
    try:
        async with factory() as session:
            row = DoctorRow(username=username, password=password, real_name=real_name)
            session.add(row)
            await session.commit()
            return row.id
    finally:
        await engine.dispose()


async def _submit(http, token: str, **overrides) -> int:
    body = {"chief_complaint": "头痛：三天，伴发热"}
    body.update(overrides)
    response = await http.post("/api/v1/consults", json=body, headers=_bearer(token))
    assert response.status_code == 200
    return response.json()["data"]["id"]


async def test_create_requires_authentication(client):
    response = await client.post(
        "/api/v1/consults", json={"chief_complaint": "头痛"}
    )

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_create_is_for_patients_only(client):
    token = await _token(client, role="doctor")

    response = await client.post(
        "/api/v1/consults",
        json={"chief_complaint": "头痛"},
        headers=_bearer(token),
    )

    assert response.status_code == 403
    assert response.json()["code"] == 403


async def test_patient_submits_a_ticket_for_a_named_doctor(client, database_url):
    token = await _token(client, role="user")

    response = await client.post(
        "/api/v1/consults",
        json={"doctor_id": 1, "chief_complaint": "头痛：三天，伴发热"},
        headers=_bearer(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200
    assert isinstance(body["data"]["id"], int)

    row = await _stored_consult(database_url, body["data"]["id"])
    assert row.user_id == 1
    assert row.doctor_id == 1
    assert row.chief_complaint == "头痛：三天，伴发热"
    assert row.status == CONSULT_STATUS_PENDING


async def test_patient_may_submit_a_ticket_without_a_doctor(client, database_url):
    token = await _token(client, role="user")

    response = await client.post(
        "/api/v1/consults",
        json={"chief_complaint": "咳嗽：一周"},
        headers=_bearer(token),
    )

    assert response.status_code == 200
    row = await _stored_consult(database_url, response.json()["data"]["id"])
    assert row.doctor_id is None
    assert row.status == CONSULT_STATUS_PENDING


@pytest.mark.parametrize(
    "body",
    [
        {"doctor_id": 1},
        {"chief_complaint": ""},
        {"doctor_id": "not-a-number", "chief_complaint": "头痛"},
    ],
)
async def test_create_rejects_invalid_fields_with_422(client, body):
    token = await _token(client, role="user")

    response = await client.post(
        "/api/v1/consults", json=body, headers=_bearer(token)
    )

    assert response.status_code == 422
    assert response.json()["code"] == 422


async def _seed_consult(
    database_url: str,
    *,
    user_id: int,
    doctor_id: int | None = None,
    chief_complaint: str = "头痛：三天",
    status: int = CONSULT_STATUS_PENDING,
    replies: list[tuple[int, str]] | None = None,
) -> int:
    engine, factory = await _new_engine(database_url)
    try:
        async with factory() as session:
            row = DoctorConsultRow(
                user_id=user_id,
                doctor_id=doctor_id,
                chief_complaint=chief_complaint,
                status=status,
            )
            session.add(row)
            await session.flush()
            for doctor, content in replies or []:
                session.add(
                    DoctorReplyRow(
                        consult_id=row.id, doctor_id=doctor, content=content
                    )
                )
            await session.commit()
            return row.id
    finally:
        await engine.dispose()


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


async def test_my_consults_requires_authentication(client):
    response = await client.get("/api/v1/consults/my")

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_my_consults_is_for_patients_only(client):
    token = await _token(client, role="doctor")

    response = await client.get("/api/v1/consults/my", headers=_bearer(token))

    assert response.status_code == 403
    assert response.json()["code"] == 403


async def test_my_consults_returns_own_tickets_with_all_replies(client, database_url):
    first = await _seed_consult(
        database_url,
        user_id=1,
        doctor_id=1,
        chief_complaint="头痛：三天，伴发热",
        status=CONSULT_STATUS_REPLIED,
        replies=[(1, "建议就诊神经内科。"), (1, "多休息。")],
    )
    other_id, _ = await _register_patient(client, "other", "李四")
    await _seed_consult(database_url, user_id=other_id, chief_complaint="咳嗽：一周")
    token = await _token(client, role="user")

    response = await client.get("/api/v1/consults/my", headers=_bearer(token))

    assert response.status_code == 200
    items = response.json()["data"]
    assert [item["id"] for item in items] == [first]
    consult = items[0]
    assert consult["user_id"] == 1
    assert consult["user_name"] == "张三"
    assert consult["doctor_id"] == 1
    assert consult["doctor_name"] == "李医生"
    assert consult["chief_complaint"] == "头痛：三天，伴发热"
    assert consult["status"] == CONSULT_STATUS_REPLIED
    assert [reply["content"] for reply in consult["replies"]] == [
        "建议就诊神经内科。",
        "多休息。",
    ]
    assert consult["replies"][0]["doctor_name"] == "李医生"


async def test_my_consults_keeps_an_unassigned_ticket_pending(client, database_url):
    consult_id = await _seed_consult(
        database_url, user_id=1, chief_complaint="咳嗽：一周"
    )
    token = await _token(client, role="user")

    response = await client.get("/api/v1/consults/my", headers=_bearer(token))

    assert response.status_code == 200
    consult = next(item for item in response.json()["data"] if item["id"] == consult_id)
    assert consult["doctor_id"] is None
    assert consult["doctor_name"] is None
    assert consult["status"] == CONSULT_STATUS_PENDING
    assert consult["replies"] == []


async def test_my_consults_is_empty_for_a_patient_without_any(client):
    _, token = await _register_patient(client, "fresh", "新患者")

    response = await client.get("/api/v1/consults/my", headers=_bearer(token))

    assert response.status_code == 200
    assert response.json()["data"] == []


async def test_pending_requires_authentication(client):
    response = await client.get("/api/v1/consults/pending")

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_pending_is_for_doctors_only(client):
    token = await _token(client, role="user")

    response = await client.get("/api/v1/consults/pending", headers=_bearer(token))

    assert response.status_code == 403
    assert response.json()["code"] == 403


async def test_pending_is_assigned_to_me_or_unassigned_and_still_open(
    client, database_url
):
    await _seed_doctor(
        database_url, username="doc2", password="doctor-pass", real_name="王医生"
    )
    mine = await _seed_consult(database_url, user_id=1, doctor_id=1)
    unassigned = await _seed_consult(database_url, user_id=1, doctor_id=None)
    await _seed_consult(database_url, user_id=1, doctor_id=2)  # 他人已指派
    await _seed_consult(
        database_url,
        user_id=1,
        doctor_id=1,
        status=CONSULT_STATUS_REPLIED,
        replies=[(1, "已回复")],
    )  # 指派给我但已回复
    token = await _token(client, role="doctor")

    response = await client.get("/api/v1/consults/pending", headers=_bearer(token))

    assert response.status_code == 200
    items = response.json()["data"]
    assert {item["id"] for item in items} == {mine, unassigned}
    assert all(item["status"] == CONSULT_STATUS_PENDING for item in items)


async def test_pending_is_empty_for_a_doctor_with_nothing_open(client, database_url):
    await _seed_doctor(
        database_url, username="doc2", password="doctor-pass", real_name="王医生"
    )
    token = await _token(client, role="doctor", username="doc2")

    response = await client.get("/api/v1/consults/pending", headers=_bearer(token))

    assert response.status_code == 200
    assert response.json()["data"] == []


async def _reply(http, token: str, consult_id: int, content: str = "请及时就医。"):
    return await http.post(
        f"/api/v1/consults/{consult_id}/replies",
        json={"consult_id": consult_id, "content": content},
        headers=_bearer(token),
    )


async def test_reply_requires_authentication(client):
    response = await client.post(
        "/api/v1/consults/1/replies",
        json={"consult_id": 1, "content": "请及时就医。"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_reply_is_for_doctors_only(client, database_url):
    consult_id = await _seed_consult(database_url, user_id=1)
    token = await _token(client, role="user")

    response = await _reply(client, token, consult_id)

    assert response.status_code == 403
    assert response.json()["code"] == 403


async def test_reply_to_a_missing_ticket_is_404(client):
    token = await _token(client, role="doctor")

    response = await _reply(client, token, 9999)

    assert response.status_code == 404
    assert response.json()["code"] == 404


async def test_first_reply_claims_an_unassigned_ticket(client, database_url):
    consult_id = await _seed_consult(database_url, user_id=1, doctor_id=None)
    token = await _token(client, role="doctor")

    response = await _reply(client, token, consult_id, "建议就诊。")

    assert response.status_code == 200
    assert response.json()["data"] is None
    row = await _stored_consult(database_url, consult_id)
    assert row.doctor_id == 1
    assert row.status == CONSULT_STATUS_REPLIED
    replies = await _stored_replies(database_url, consult_id)
    assert [(reply.doctor_id, reply.content) for reply in replies] == [
        (1, "建议就诊。")
    ]


async def test_a_doctor_may_append_more_replies_to_an_open_ticket(
    client, database_url
):
    consult_id = await _seed_consult(
        database_url,
        user_id=1,
        doctor_id=1,
        status=CONSULT_STATUS_REPLIED,
        replies=[(1, "第一条")],
    )
    token = await _token(client, role="doctor")

    response = await _reply(client, token, consult_id, "第二条")

    assert response.status_code == 200
    replies = await _stored_replies(database_url, consult_id)
    assert [reply.content for reply in replies] == ["第一条", "第二条"]
    assert (await _stored_consult(database_url, consult_id)).status == (
        CONSULT_STATUS_REPLIED
    )


async def test_replying_to_another_doctors_ticket_is_409_and_writes_nothing(
    client, database_url
):
    await _seed_doctor(
        database_url, username="doc2", password="doctor-pass", real_name="王医生"
    )
    consult_id = await _seed_consult(database_url, user_id=1, doctor_id=2)
    token = await _token(client, role="doctor")

    response = await _reply(client, token, consult_id, "抢单")

    assert response.status_code == 409
    assert response.json()["code"] == 409
    assert await _stored_replies(database_url, consult_id) == []
    row = await _stored_consult(database_url, consult_id)
    assert row.doctor_id == 2
    assert row.status == CONSULT_STATUS_PENDING


@pytest.mark.parametrize(
    "body",
    [
        {"content": "请及时就医。"},
        {"consult_id": 1, "content": ""},
    ],
)
async def test_reply_rejects_invalid_bodies_with_422(client, database_url, body):
    consult_id = await _seed_consult(database_url, user_id=1, doctor_id=1)
    token = await _token(client, role="doctor")

    response = await client.post(
        f"/api/v1/consults/{consult_id}/replies",
        json=body,
        headers=_bearer(token),
    )

    assert response.status_code == 422
    assert response.json()["code"] == 422


def _admin_query(**overrides) -> str:
    params = {"page": 1, "page_size": 10}
    params.update({key: value for key, value in overrides.items() if value is not None})
    return "?" + "&".join(f"{key}={value}" for key, value in params.items())


async def _admin_list(http, token: str, query: str = ""):
    return await http.get(f"/api/v1/consults/admin{query}", headers=_bearer(token))


async def test_admin_list_requires_authentication(client):
    response = await client.get("/api/v1/consults/admin")

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_admin_list_rejects_non_admins(client):
    for role in ("user", "doctor"):
        token = await _token(client, role=role)

        response = await _admin_list(client, token)

        assert response.status_code == 403
        assert response.json()["code"] == 403


async def test_admin_list_paginates_and_filters_by_status(client, database_url):
    pending = await _seed_consult(database_url, user_id=1, chief_complaint="头痛：三天")
    replied = await _seed_consult(
        database_url,
        user_id=1,
        doctor_id=1,
        chief_complaint="咳嗽：一周",
        status=CONSULT_STATUS_REPLIED,
        replies=[(1, "多休息。")],
    )
    await _seed_consult(database_url, user_id=1, chief_complaint="发热：两天")
    token = await _token(client, role="admin")

    first = (await _admin_list(client, token, _admin_query(page_size=2))).json()
    assert first["data"]["total"] == 3
    assert first["data"]["page"] == 1
    assert first["data"]["page_size"] == 2
    assert len(first["data"]["items"]) == 2

    second = (
        await _admin_list(client, token, _admin_query(page=2, page_size=2))
    ).json()
    assert len(second["data"]["items"]) == 1

    by_status = (
        await _admin_list(
            client, token, _admin_query(status=CONSULT_STATUS_REPLIED)
        )
    ).json()
    assert [item["id"] for item in by_status["data"]["items"]] == [replied]
    assert by_status["data"]["items"][0]["replies"][0]["content"] == "多休息。"

    open_only = (
        await _admin_list(
            client, token, _admin_query(status=CONSULT_STATUS_PENDING)
        )
    ).json()
    assert {item["id"] for item in open_only["data"]["items"]} == {pending, 3}


async def test_admin_list_rejects_out_of_range_query(client):
    token = await _token(client, role="admin")

    response = await _admin_list(client, token, _admin_query(page=0))

    assert response.status_code == 422
    assert response.json()["code"] == 422


async def _delete(http, token: str, consult_id: int):
    return await http.delete(
        f"/api/v1/consults/admin/{consult_id}", headers=_bearer(token)
    )


async def test_delete_requires_authentication(client):
    response = await client.delete("/api/v1/consults/admin/1")

    assert response.status_code == 401
    assert response.json()["code"] == 401


async def test_delete_is_for_admins_only(client):
    for role in ("user", "doctor"):
        token = await _token(client, role=role)

        response = await _delete(client, token, 1)

        assert response.status_code == 403
        assert response.json()["code"] == 403


async def test_admin_delete_removes_the_ticket_and_its_replies(client, database_url):
    consult_id = await _seed_consult(
        database_url,
        user_id=1,
        doctor_id=1,
        status=CONSULT_STATUS_REPLIED,
        replies=[(1, "第一条"), (1, "第二条")],
    )
    token = await _token(client, role="admin")

    response = await _delete(client, token, consult_id)

    assert response.status_code == 200
    assert response.json()["data"] is None
    assert await _stored_consult(database_url, consult_id) is None
    assert await _stored_replies(database_url, consult_id) == []


async def test_delete_of_a_missing_ticket_is_404(client):
    token = await _token(client, role="admin")

    response = await _delete(client, token, 9999)

    assert response.status_code == 404
    assert response.json()["code"] == 404
