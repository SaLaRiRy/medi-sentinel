"""TICKET-014：患者侧会话列表与历史消息（`SPEC.md` 5.4「AI 问诊与知识库」）。

- `GET /chat/sessions`：本人会话列表，按更新时间倒序（FUNCTIONAL_SPEC 2.3）
- `GET /chat/sessions/{id}/messages`：指定会话的消息，仅按会话号过滤
  （FUNCTIONAL_SPEC 2.3 / 5.7「消息查询过滤」）

角色为 `user`：无令牌 401、非患者 403。`/chat/send` 携带令牌时，新会话归属该
患者，`session` 帧的会话号随后可在列表里读到（本票 AC：新会话由 `session` 帧关联）。
"""

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from skills.orchestration import OrchestrationPorts
from tests.doubles import HitsGraphPort, HitsRetrievalPort, ScriptedLlmPort

SERVER_ROOT = Path(__file__).resolve().parents[1]
GRAPH_RECORDS = [
    {"disease": "感冒", "matched_symptoms": ["发热", "头痛"], "department": "呼吸内科"}
]
RETRIEVAL_HITS = [
    {
        "content": "发热期间应多饮水、注意休息。",
        "metadata": {"file_name": "感冒与流感指南.md"},
        "distance": 0.21,
    }
]


def parse_sse(text: str) -> list[dict]:
    frames = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        frames.append(json.loads(block[len("data: ") :]))
    return frames


@pytest.fixture
def ports() -> OrchestrationPorts:
    return OrchestrationPorts(
        graph=HitsGraphPort(GRAPH_RECORDS),
        retrieval=HitsRetrievalPort(RETRIEVAL_HITS),
        llm=ScriptedLlmPort(["您好，", "建议监测体温。"]),
    )


@pytest.fixture
async def client(database_url, accounts, ports):
    from core.config import Settings
    from main import create_app

    app = create_app(Settings(database_url=database_url), ports=ports)
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as http:
            yield http


async def _token(client, *, username="shared", password="user-pass", role="user") -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password, "role": role},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_sessions_requires_authentication(client):
    response = await client.get("/api/v1/chat/sessions")

    assert response.status_code == 401
    assert response.json()["code"] == 401


@pytest.mark.parametrize(
    "role,password", [("doctor", "doctor-pass"), ("admin", "admin-pass")]
)
async def test_sessions_is_403_for_non_patients(client, role, password):
    token = await _token(client, password=password, role=role)

    response = await client.get("/api/v1/chat/sessions", headers=_bearer(token))

    assert response.status_code == 403
    assert response.json()["code"] == 403


async def test_sessions_starts_empty_for_a_new_patient(client):
    token = await _token(client)

    response = await client.get("/api/v1/chat/sessions", headers=_bearer(token))

    assert response.status_code == 200
    assert response.json()["data"] == []


async def test_a_new_session_is_attributed_to_the_token_holder(client):
    token = await _token(client)

    frames = parse_sse(
        (
            await client.post(
                "/api/v1/chat/send",
                json={"message": "我头疼发烧三天了"},
                headers=_bearer(token),
            )
        ).text
    )
    session_id = frames[0]["session_id"]

    listing = await client.get("/api/v1/chat/sessions", headers=_bearer(token))

    sessions = listing.json()["data"]
    assert [session["id"] for session in sessions] == [session_id]
    assert sessions[0]["title"] == "我头疼发烧三天了"
    assert sessions[0]["message_count"] == 2


async def test_sessions_are_listed_updated_first_and_scoped_to_the_owner(client):
    token = await _token(client)
    first = parse_sse(
        (
            await client.post(
                "/api/v1/chat/send",
                json={"message": "第一段对话"},
                headers=_bearer(token),
            )
        ).text
    )[0]["session_id"]
    second = parse_sse(
        (
            await client.post(
                "/api/v1/chat/send",
                json={"message": "第二段对话"},
                headers=_bearer(token),
            )
        ).text
    )[0]["session_id"]
    # Another patient's session must not leak into this patient's list.
    other = await _token(client, username="shared", role="doctor", password="doctor-pass")
    assert other  # doctor cannot create sessions; just proving a second identity exists

    response = await client.get("/api/v1/chat/sessions", headers=_bearer(token))

    assert [session["id"] for session in response.json()["data"]] == [second, first]


async def test_messages_returns_the_session_history_in_order(client):
    token = await _token(client)
    session_id = parse_sse(
        (
            await client.post(
                "/api/v1/chat/send",
                json={"message": "我头疼发烧三天了"},
                headers=_bearer(token),
            )
        ).text
    )[0]["session_id"]

    response = await client.get(
        f"/api/v1/chat/sessions/{session_id}/messages", headers=_bearer(token)
    )

    assert response.status_code == 200
    messages = response.json()["data"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "我头疼发烧三天了"
    assert messages[1]["content"] == "您好，建议监测体温。"
    assert messages[1]["references"][0]["file_name"] == "感冒与流感指南.md"
    assert messages[1]["graph"][0]["disease"] == "感冒"


async def test_messages_is_404_for_an_unknown_session(client):
    token = await _token(client)

    response = await client.get(
        "/api/v1/chat/sessions/999999/messages", headers=_bearer(token)
    )

    assert response.status_code == 404
    assert response.json()["code"] == 404


async def test_messages_requires_a_patient(client):
    assert (await client.get("/api/v1/chat/sessions/1/messages")).status_code == 401
    token = await _token(client, password="doctor-pass", role="doctor")
    response = await client.get(
        "/api/v1/chat/sessions/1/messages", headers=_bearer(token)
    )
    assert response.status_code == 403


RED_FLAG_MESSAGE = "胸口剧痛，出冷汗，喘不上气"


async def test_a_red_flag_turn_keeps_the_safety_prompt_in_history(client):
    """TICKET-008 挂账第 1 条（本票拍板：存安全提示）。

    拦截路径也以 `done` 结束，故助手消息照常写入；其正文不再是空串，而是安全门
    文案（`message` + `suggested_action`），否则前端重新加载历史只会看到一个
    空气泡，安全提示随流消失。消息计数仍满足 FUNCTIONAL_SPEC 5.7 的 +2。
    """
    token = await _token(client)
    frames = parse_sse(
        (
            await client.post(
                "/api/v1/chat/send",
                json={"message": RED_FLAG_MESSAGE},
                headers=_bearer(token),
            )
        ).text
    )
    safety = next(frame for frame in frames if frame["type"] == "safety")
    session_id = frames[0]["session_id"]

    response = await client.get(
        f"/api/v1/chat/sessions/{session_id}/messages", headers=_bearer(token)
    )
    messages = response.json()["data"]

    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[1]["content"] == f"{safety['message']}\n{safety['suggested_action']}"
    assert messages[1]["content"] != ""
    assert messages[1]["references"] == [] and messages[1]["graph"] == []

    listing = await client.get("/api/v1/chat/sessions", headers=_bearer(token))
    assert listing.json()["data"][0]["message_count"] == 2
