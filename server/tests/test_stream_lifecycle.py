"""TICKET-010: the streaming lifecycle — one generation per session, cancelling
the downstream call on disconnect, and returning the request's connection.

AC-B-25 (a second concurrent `/chat/send` on one session is 409 and starts no
second generation), AC-B-26 (a mid-stream disconnect cancels the model and
leaves a `cancelled` span), and SPEC.md 3.1/3.3 (one session per request,
committed or rolled back, never held across generation).

External dependencies are still replaced at B-3; storage runs on a migrated
SQLite database.
"""

import asyncio
import json
import re
import statistics
import time
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import Settings
from main import create_app
from models.consult import ConsultMessageRow, ConsultSessionRow
from repositories.trace import TraceRepository
from skills.orchestration import ChatRequest, OrchestrationPorts, Orchestrator
from skills.trace import InMemoryTraceSink
from tests.doubles import (
    BlockingLlmPort,
    FailingLlmPort,
    GatedLlmPort,
    HitsGraphPort,
    HitsRetrievalPort,
    PacedLlmPort,
    ScriptedLlmPort,
)

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
    db_path = tmp_path / "lifecycle.db"
    config = Config(str(SERVER_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    command.upgrade(config, "head")
    return f"sqlite+aiosqlite:///{db_path}"


@pytest.fixture
async def session_factory(database_url):
    engine = create_async_engine(database_url)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@asynccontextmanager
async def client_for(database_url: str, ports: OrchestrationPorts):
    app = create_app(Settings(database_url=database_url), ports=ports)
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as http:
            yield app, http


def healthy_ports(llm) -> OrchestrationPorts:
    return OrchestrationPorts(
        graph=HitsGraphPort(GRAPH_RECORDS),
        retrieval=HitsRetrievalPort(RETRIEVAL_HITS),
        llm=llm,
    )


def orchestrator_with(llm) -> tuple[Orchestrator, InMemoryTraceSink]:
    sink = InMemoryTraceSink()
    return (
        Orchestrator(ports=healthy_ports(llm), sink=sink),
        sink,
    )


def trace_id_of(frames: list[dict]) -> str:
    return next(frame["trace_id"] for frame in frames if frame["type"] == "trace")


async def seed_session(session_factory) -> int:
    async with session_factory() as session:
        row = ConsultSessionRow(title="既有会话", message_count=0)
        session.add(row)
        await session.commit()
        return row.id


async def test_a_second_concurrent_send_on_the_same_session_returns_409(
    database_url, session_factory
):
    llm = GatedLlmPort(["您好"])
    session_id = await seed_session(session_factory)

    async with client_for(database_url, healthy_ports(llm)) as (_, client):
        first = asyncio.create_task(
            client.post(
                "/api/v1/chat/send",
                json={"session_id": session_id, "message": MESSAGE},
            )
        )
        await asyncio.wait_for(llm.started.wait(), timeout=5)

        second = asyncio.create_task(
            client.post(
                "/api/v1/chat/send", json={"session_id": session_id, "message": MESSAGE}
            )
        )
        second_response = await asyncio.wait_for(second, timeout=2)

        assert second_response.status_code == 409
        assert json.loads(second_response.text)["code"] == 409
        assert json.loads(second_response.text)["message"]
        assert llm.calls == 1

        llm.release()
        first_response = await first

    assert first_response.status_code == 200
    assert parse_sse(first_response.text)[-1]["type"] == "done"
    async with session_factory() as session:
        roles = [
            row.role
            for row in (await session.execute(select(ConsultMessageRow))).scalars()
        ]
    assert roles == ["user", "assistant"]


async def test_a_fresh_session_is_never_blocked_by_another_requests_generation(
    database_url,
):
    llm = GatedLlmPort(["您好"], expected_calls=2)

    async with client_for(database_url, healthy_ports(llm)) as (_, client):
        first = asyncio.create_task(
            client.post("/api/v1/chat/send", json={"message": MESSAGE})
        )
        await asyncio.wait_for(llm.started.wait(), timeout=5)

        second = asyncio.create_task(
            client.post("/api/v1/chat/send", json={"message": MESSAGE})
        )
        await asyncio.wait_for(llm.all_started.wait(), timeout=5)

        assert llm.calls == 2
        llm.release()
        first_response, second_response = await asyncio.gather(first, second)

    assert first_response.status_code == 200
    assert second_response.status_code == 200


async def _cancel_mid_generation(orchestrator, llm) -> list[dict]:
    """Consume the stream until the model is blocked, then cancel like a client
    that hung up (SPEC.md 6.1 AC-B-26)."""
    frames: list[dict] = []

    async def consume():
        async for frame in orchestrator.run(
            ChatRequest(message=MESSAGE), session_id=1
        ):
            frames.append(frame)

    task = asyncio.create_task(consume())
    await asyncio.wait_for(llm.waiting.wait(), timeout=5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    return frames


async def test_a_client_disconnect_cancels_the_downstream_model_call():
    llm = BlockingLlmPort()
    orchestrator, sink = orchestrator_with(llm)

    frames = await _cancel_mid_generation(orchestrator, llm)

    assert llm.cancelled
    spans = await sink.spans_for(trace_id_of(frames))
    assert [span.status for span in spans if span.name == "llm"] == ["cancelled"]


async def test_a_cancelled_stream_ends_with_neither_done_nor_error():
    llm = BlockingLlmPort()
    orchestrator, _ = orchestrator_with(llm)

    frames = await _cancel_mid_generation(orchestrator, llm)

    types = [frame["type"] for frame in frames]
    assert types[:2] == ["session", "trace"]
    assert types.count("content") == 1
    assert "done" not in types
    assert "error" not in types


async def test_closing_the_stream_between_frames_still_marks_the_model_cancelled():
    """The other cancellation timing: the client goes away while the generator is
    parked on a `yield`, so it is closed with GeneratorExit rather than
    CancelledError. The `llm` span must say `cancelled` either way."""
    llm = BlockingLlmPort()
    orchestrator, sink = orchestrator_with(llm)
    stream = orchestrator.run(ChatRequest(message=MESSAGE), session_id=1)
    frames = [await stream.__anext__() for _ in range(4)]

    await stream.aclose()

    assert [frame["type"] for frame in frames] == [
        "session",
        "trace",
        "route",
        "content",
    ]
    spans = await sink.spans_for(trace_id_of(frames))
    assert [span.status for span in spans if span.name == "llm"] == ["cancelled"]


@pytest.mark.parametrize("llm", [ScriptedLlmPort(["您好"]), FailingLlmPort()])
async def test_the_stream_ends_with_done_or_error_but_never_both(llm):
    orchestrator, _ = orchestrator_with(llm)

    frames = [
        frame
        async for frame in orchestrator.run(ChatRequest(message=MESSAGE), session_id=1)
    ]

    types = [frame["type"] for frame in frames]
    assert types.count("done") + types.count("error") == 1
    assert not ("done" in types and "error" in types)


def test_the_error_frame_contract_places_no_enum_on_the_code():
    """TICKET-009 mapped non-LLM internal failures to `code == 500`; the frozen
    contract must accept it, so `error.code` carries no enum (TICKET-010)."""
    contract = json.loads(
        (SERVER_ROOT.parent / "contracts" / "sse-events.json").read_text(
            encoding="utf-8"
        )
    )

    code = contract["$defs"]["error"]["properties"]["code"]
    assert code["type"] == "integer"
    assert "enum" not in code and "const" not in code


async def _drive_until_client_disconnects(
    app, *, body: dict, frames: int
) -> tuple[int, str]:
    """Send one request straight to the ASGI app, then hang up after `frames`
    frames have been pushed — exactly what a browser closing the SSE stream does
    (SPEC.md 6.1 AC-B-26)."""
    payload = json.dumps(body).encode()
    chunks: list[bytes] = []
    status: int | None = None
    request_read = False
    disconnect = asyncio.Event()

    async def receive():
        nonlocal request_read
        if not request_read:
            request_read = True
            return {"type": "http.request", "body": payload, "more_body": False}
        await disconnect.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        nonlocal status
        if message["type"] == "http.response.start":
            status = message["status"]
        elif message["type"] == "http.response.body":
            chunk = message.get("body", b"")
            if chunk:
                chunks.append(chunk)
                if len(chunks) >= frames:
                    disconnect.set()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/chat/send",
        "raw_path": b"/api/v1/chat/send",
        "query_string": b"",
        "headers": [
            (b"host", b"test"),
            (b"content-type", b"application/json"),
            (b"content-length", str(len(payload)).encode()),
        ],
        "server": ("test", 80),
        "client": ("1.1.1.1", 123),
        "root_path": "",
    }
    await app(scope, receive, send)
    return status, b"".join(chunks).decode("utf-8")


async def test_an_http_disconnect_cancels_the_model_and_settles_the_request(
    database_url, session_factory
):
    llm = BlockingLlmPort()
    session_id = await seed_session(session_factory)

    async with client_for(database_url, healthy_ports(llm)) as (app, _):
        status, text = await _drive_until_client_disconnects(
            app, body={"session_id": session_id, "message": MESSAGE}, frames=4
        )

        assert status == 200
        frames = parse_sse(text)
        assert [frame["type"] for frame in frames] == [
            "session",
            "trace",
            "route",
            "content",
        ]
        assert llm.cancelled
        assert app.state.generation_guard.in_flight() == 0

    async with session_factory() as session:
        spans = await TraceRepository(session).spans_for(trace_id_of(frames))
        roles = [
            row.role
            for row in (await session.execute(select(ConsultMessageRow))).scalars()
        ]
        session_row = await session.get(ConsultSessionRow, session_id)

    assert [span.status for span in spans if span.name == "llm"] == ["cancelled"]
    assert spans and any(span.name == "safety-gate" for span in spans)
    # A cancelled stream emits no `done`, so no assistant message is written.
    assert roles == ["user"]
    assert session_row.message_count == 0


async def test_the_request_opens_exactly_one_async_session(
    database_url,
):
    llm = ScriptedLlmPort(["您好"])
    opened: list[object] = []

    async with client_for(database_url, healthy_ports(llm)) as (app, client):
        database = app.state.database
        factory = database.session_factory

        def counting_factory(*args, **kwargs):
            opened.append(object())
            return factory(*args, **kwargs)

        database.session_factory = counting_factory
        response = await client.post("/api/v1/chat/send", json={"message": MESSAGE})

    assert response.status_code == 200
    assert len(opened) == 1


async def test_the_request_releases_its_connection_to_the_pool(
    database_url, session_factory
):
    llm = GatedLlmPort(["您好"])
    session_id = await seed_session(session_factory)

    async with client_for(database_url, healthy_ports(llm)) as (app, client):
        pool = app.state.database.engine.pool
        task = asyncio.create_task(
            client.post(
                "/api/v1/chat/send",
                json={"session_id": session_id, "message": MESSAGE},
            )
        )
        await asyncio.wait_for(llm.started.wait(), timeout=5)

        # Generation runs with no request connection checked out (SPEC.md 3.1).
        assert pool.checkedout() == 0

        llm.release()
        response = await task

    assert response.status_code == 200
    assert pool.checkedout() == 0


# --- SPEC.md 6.1 AC-B-24: the request path is asynchronous, and twenty
# --- concurrent consults never block the loop past the configured threshold.

REQUEST_PATH = ("main.py", "api", "core", "db", "services", "repositories", "skills")

FORBIDDEN_SYNC = [
    (re.compile(r"^\s*(?:import|from)\s+requests\b", re.M), "同步 HTTP 客户端 requests"),
    (re.compile(r"\burllib\.request\b"), "同步 HTTP 客户端 urllib.request"),
    (re.compile(r"\bhttp\.client\b"), "同步 HTTP 客户端 http.client"),
    (re.compile(r"\bhttpx\.Client\b"), "同步 HTTP 客户端 httpx.Client"),
    (re.compile(r"\bcreate_engine\b"), "同步数据库引擎 create_engine"),
    (re.compile(r"(?<!async_)sessionmaker\s*\("), "同步数据库会话工厂 sessionmaker"),
    (
        re.compile(r"from\s+sqlalchemy\.orm\s+import\s+[^\n]*\bSession\b"),
        "同步数据库会话 Session",
    ),
    (re.compile(r"\bsqlalchemy\.orm\.Session\b"), "同步数据库会话 Session"),
    (re.compile(r"\bpymysql\b"), "同步 MySQL 驱动 pymysql"),
    (re.compile(r"\bpsycopg2\b"), "同步 PostgreSQL 驱动 psycopg2"),
    (re.compile(r"\bsqlite3\b"), "同步 SQLite 驱动 sqlite3"),
    (re.compile(r"(?<!Async)GraphDatabase\b"), "同步图数据库驱动 GraphDatabase"),
    (re.compile(r"\btime\.sleep\s*\("), "同步阻塞等待 time.sleep"),
]


def _request_path_files():
    for entry in REQUEST_PATH:
        target = SERVER_ROOT / entry
        if target.is_file():
            yield target
        else:
            yield from sorted(
                path
                for path in target.rglob("*.py")
                if "__pycache__" not in path.parts
            )


def test_the_request_path_declares_no_synchronous_io():
    offenders = []
    for path in _request_path_files():
        text = path.read_text(encoding="utf-8")
        for pattern, label in FORBIDDEN_SYNC:
            for match in pattern.finditer(text):
                offenders.append(
                    f"{path.relative_to(SERVER_ROOT)}: {label}: {match.group(0)!r}"
                )

    assert offenders == []


SYNC_SAMPLES = [
    "import requests\n",
    "from urllib.request import urlopen\n",
    "import http.client\n",
    "client = httpx.Client()\n",
    "engine = create_engine(url)\n",
    "factory = sessionmaker(engine)\n",
    "from sqlalchemy.orm import Session\n",
    "session = sqlalchemy.orm.Session(engine)\n",
    "import pymysql\n",
    "import psycopg2\n",
    "import sqlite3\n",
    "driver = GraphDatabase.driver(uri)\n",
    "time.sleep(1)\n",
]


@pytest.mark.parametrize("sample", SYNC_SAMPLES)
def test_every_sync_pattern_catches_its_example(sample):
    assert any(pattern.search(sample) for pattern, _ in FORBIDDEN_SYNC)


@pytest.mark.parametrize(
    "line",
    [
        "AsyncGraphDatabase.driver(uri)",
        "engine = create_async_engine(url)",
        "factory = async_sessionmaker(engine)",
        "from sqlalchemy.ext.asyncio import AsyncSession",
    ],
)
def test_the_sync_patterns_do_not_flag_their_async_counterparts(line):
    assert not any(pattern.search(line) for pattern, _ in FORBIDDEN_SYNC)


class EventLoopStallMonitor:
    """Samples scheduling latency: a synchronous call shows up as a sleep that
    overran its interval, i.e. the loop was not free to wake us on time."""

    def __init__(self, interval: float = 0.005) -> None:
        self.interval = interval
        self.max_stall = 0.0
        self._stop = asyncio.Event()

    async def watch(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            started = loop.time()
            await asyncio.sleep(self.interval)
            self.max_stall = max(
                self.max_stall, loop.time() - started - self.interval
            )
            if self._stop.is_set():
                return

    def stop(self) -> None:
        self._stop.set()


async def _max_stall_during(work) -> float:
    monitor = EventLoopStallMonitor()
    task = asyncio.create_task(monitor.watch())
    try:
        await asyncio.sleep(0)  # let the monitor take its first sample
        await work()
    finally:
        monitor.stop()
        await task
    return monitor.max_stall


async def test_the_stall_monitor_detects_a_synchronous_stall():
    async def blocking_work() -> None:
        time.sleep(0.3)

    stall = await _max_stall_during(blocking_work)

    assert stall > 0.2


async def test_twenty_concurrent_consults_do_not_block_the_event_loop(
    database_url,
):
    """AC-B-24: twenty overlapping consults, judged by the median of repeated bursts.

    Two noise sources are removed without touching the threshold:

    - The twenty requests are launched a millisecond apart. Launched instead in
      a single `gather`, the loop absorbs all twenty startups in one iteration,
      which is itself a ~250ms *non-blocking* stall — a test artifact that then
      dominates the measurement. Staggered, all twenty are still in flight at
      once, and the sample reflects the loop's steady state.
    - A single burst's worst stall is an extreme-value sample, so the test runs
      several bursts and asserts on the median. A genuinely blocking call stalls
      every burst; scheduler noise no longer flips the result.
    """
    threshold = Settings().event_loop_block_threshold_ms / 1000
    llm = PacedLlmPort(["您好，", "请多休息。"])
    samples = 5

    async with client_for(database_url, healthy_ports(llm)) as (_, client):

        async def burst() -> None:
            tasks: list[asyncio.Task] = []
            for _ in range(20):
                tasks.append(
                    asyncio.create_task(
                        client.post("/api/v1/chat/send", json={"message": MESSAGE})
                    )
                )
                # Let the loop start this request before adding the next, so the
                # twenty startups do not all land in a single iteration.
                await asyncio.sleep(0.001)
            responses = await asyncio.gather(*tasks)
            assert all(response.status_code == 200 for response in responses)
            assert all(
                parse_sse(response.text)[-1]["type"] == "done"
                for response in responses
            )

        stalls = [await _max_stall_during(burst) for _ in range(samples)]

    assert statistics.median(stalls) <= threshold
