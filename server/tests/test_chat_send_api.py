"""The HTTP half of the milestone: `POST /api/v1/chat/send` streams one consult
as SSE and applies FUNCTIONAL_SPEC 5.7's session/message rules.

External dependencies are still replaced at B-3; storage runs on a migrated
SQLite database so the seam under test is the route plus B-5.
"""

import json
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models.consult import ConsultMessageRow, ConsultSessionRow
from skills.orchestration import OrchestrationPorts
from tests.doubles import HitsGraphPort, HitsRetrievalPort, ScriptedLlmPort

SERVER_ROOT = Path(__file__).resolve().parents[1]
MESSAGE = "我头疼发烧三天了"
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
        assert block.startswith("data: ")
        frames.append(json.loads(block[len("data: ") :]))
    return frames


@pytest.fixture
def database_url(tmp_path) -> str:
    db_path = tmp_path / "chat.db"
    config = Config(str(SERVER_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    command.upgrade(config, "head")
    return f"sqlite+aiosqlite:///{db_path}"


@pytest.fixture
def ports() -> OrchestrationPorts:
    return OrchestrationPorts(
        graph=HitsGraphPort(GRAPH_RECORDS),
        retrieval=HitsRetrievalPort(RETRIEVAL_HITS),
        llm=ScriptedLlmPort(["您好，", "建议监测体温。"]),
    )


@pytest.fixture
async def client(database_url, ports):
    from core.config import Settings
    from main import create_app

    app = create_app(Settings(database_url=database_url), ports=ports)
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as http:
            yield http


@pytest.fixture
async def session_factory(database_url):
    engine = create_async_engine(database_url)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def test_chat_send_streams_the_documented_frames_as_sse(client):
    response = await client.post("/api/v1/chat/send", json={"message": MESSAGE})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    frames = parse_sse(response.text)
    assert [frame["type"] for frame in frames] == [
        "session",
        "trace",
        "route",
        "content",
        "content",
        "done",
    ]
    assert frames[3]["content"] == "您好，"
    assert frames[-1]["references"] and frames[-1]["graph"]


async def test_new_session_gets_its_title_from_the_first_20_characters(
    client, session_factory
):
    long_message = "我" * 25

    response = await client.post("/api/v1/chat/send", json={"message": long_message})
    session_id = parse_sse(response.text)[0]["session_id"]

    async with session_factory() as session:
        row = await session.get(ConsultSessionRow, session_id)
    assert row is not None
    assert row.title == "我" * 20 + "..."


async def test_short_message_is_used_as_the_title_without_an_ellipsis(
    client, session_factory
):
    response = await client.post("/api/v1/chat/send", json={"message": MESSAGE})
    session_id = parse_sse(response.text)[0]["session_id"]

    async with session_factory() as session:
        row = await session.get(ConsultSessionRow, session_id)
    assert row.title == MESSAGE


async def test_a_completed_turn_stores_both_messages_and_adds_two_to_the_count(
    client, session_factory
):
    response = await client.post("/api/v1/chat/send", json={"message": MESSAGE})
    session_id = parse_sse(response.text)[0]["session_id"]
    done = parse_sse(response.text)[-1]

    async with session_factory() as session:
        consult_session = await session.get(ConsultSessionRow, session_id)
        messages = (
            (await session.execute(
                select(ConsultMessageRow)
                .where(ConsultMessageRow.session_id == session_id)
                .order_by(ConsultMessageRow.id)
            ))
            .scalars()
            .all()
        )

    assert consult_session.message_count == 2
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[0].content == MESSAGE
    assert messages[1].content == "您好，建议监测体温。"
    assert messages[1].cost_time == done["cost_time"]
    assert json.loads(messages[1].references_json)[0]["file_name"] == "感冒与流感指南.md"
    assert json.loads(messages[1].graph_json)[0]["disease"] == "感冒"


async def test_an_existing_session_keeps_its_title_and_accumulates_messages(
    client, session_factory
):
    first = parse_sse(
        (await client.post("/api/v1/chat/send", json={"message": MESSAGE})).text
    )
    session_id = first[0]["session_id"]

    second = parse_sse(
        (
            await client.post(
                "/api/v1/chat/send",
                json={"session_id": session_id, "message": "现在还有点咳嗽"},
            )
        ).text
    )

    assert second[0]["session_id"] == session_id
    async with session_factory() as session:
        row = await session.get(ConsultSessionRow, session_id)
    assert row.title == MESSAGE
    assert row.message_count == 4


async def test_only_the_most_recent_six_prior_messages_reach_the_model(
    client, session_factory, ports
):
    async with session_factory() as session:
        row = ConsultSessionRow(title="旧会话", message_count=8)
        session.add(row)
        await session.flush()
        for index in range(8):
            session.add(
                ConsultMessageRow(
                    session_id=row.id,
                    role="user" if index % 2 == 0 else "assistant",
                    content=f"历史{index}",
                )
            )
        await session.commit()
        session_id = row.id

    await client.post(
        "/api/v1/chat/send",
        json={"session_id": session_id, "message": "现在的问题"},
    )

    prompt = ports.llm.prompts[0]
    assert "历史2" in prompt and "历史7" in prompt
    assert "历史0" not in prompt and "历史1" not in prompt
    assert "现在的问题" in prompt


async def test_an_unknown_session_id_starts_a_new_session_instead_of_failing(client):
    frames = parse_sse(
        (
            await client.post(
                "/api/v1/chat/send",
                json={"session_id": 999_999, "message": MESSAGE},
            )
        ).text
    )

    assert frames[0]["session_id"] != 999_999
    assert frames[-1]["type"] == "done"
