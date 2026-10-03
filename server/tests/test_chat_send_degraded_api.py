"""The HTTP half of TICKET-009: degraded branches and a failed generation behave
the way SPEC.md 5.2 / 5.5 fix them, over the real route and B-5 storage.

AC-E-04 lives here: with the graph unavailable, 「头疼发烧」 still answers —
HTTP 200, `done.degraded == ["graph"]`, content streamed. Generation cannot
degrade, so it ends in an `error` frame (503 unavailable, 504 timeout) and never
stores an assistant message.
"""

import json
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models.consult import ConsultMessageRow, ConsultSessionRow
from skills.orchestration import OrchestrationPorts
from tests.doubles import (
    FailingLlmPort,
    HitsRetrievalPort,
    ScriptedLlmPort,
    ThrowingGraphPort,
    TimedOutLlmPort,
)

SERVER_ROOT = Path(__file__).resolve().parents[1]
MESSAGE = "我头疼发烧三天了"
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
    db_path = tmp_path / "degraded.db"
    config = Config(str(SERVER_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    command.upgrade(config, "head")
    return f"sqlite+aiosqlite:///{db_path}"


@asynccontextmanager
async def client_for(database_url: str, ports: OrchestrationPorts):
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


async def test_graph_unavailable_still_answers_with_a_degraded_done(database_url):
    ports = OrchestrationPorts(
        graph=ThrowingGraphPort(),
        retrieval=HitsRetrievalPort(RETRIEVAL_HITS),
        llm=ScriptedLlmPort(["您好，", "建议监测体温。"]),
    )

    async with client_for(database_url, ports) as client:
        response = await client.post("/api/v1/chat/send", json={"message": MESSAGE})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    frames = parse_sse(response.text)
    assert [frame["type"] for frame in frames] == [
        "session",
        "trace",
        "route",
        "content",
        "content",
        "done",
    ]
    done = frames[-1]
    assert done["degraded"] == ["graph"]
    assert done["graph"] == []
    assert done["references"]


async def test_unavailable_generation_streams_a_503_error_frame(
    database_url, session_factory
):
    ports = OrchestrationPorts(
        graph=ThrowingGraphPort(),
        retrieval=HitsRetrievalPort(RETRIEVAL_HITS),
        llm=FailingLlmPort(),
    )

    async with client_for(database_url, ports) as client:
        response = await client.post("/api/v1/chat/send", json={"message": MESSAGE})

    assert response.status_code == 200
    frames = parse_sse(response.text)
    assert frames[-1]["type"] == "error"
    assert frames[-1]["code"] == 503
    assert frames[-1]["message"]
    assert "done" not in [frame["type"] for frame in frames]

    async with session_factory() as session:
        rows = (await session.execute(select(ConsultMessageRow))).scalars().all()
    assert [row.role for row in rows] == ["user"]


async def test_timed_out_generation_streams_a_504_error_frame(
    database_url, session_factory
):
    ports = OrchestrationPorts(
        graph=ThrowingGraphPort(),
        retrieval=HitsRetrievalPort(RETRIEVAL_HITS),
        llm=TimedOutLlmPort(),
    )

    async with client_for(database_url, ports) as client:
        response = await client.post("/api/v1/chat/send", json={"message": MESSAGE})

    assert response.status_code == 200
    frames = parse_sse(response.text)
    assert frames[-1]["type"] == "error"
    assert frames[-1]["code"] == 504
    assert frames[-1]["message"]

    async with session_factory() as session:
        session_row = (await session.execute(select(ConsultSessionRow))).scalar_one()
        roles = [
            row.role
            for row in (await session.execute(select(ConsultMessageRow))).scalars()
        ]
    # The user turn is kept; a failed generation advances neither the answer nor
    # the message count (FUNCTIONAL_SPEC 5.7).
    assert roles == ["user"]
    assert session_row.message_count == 0
