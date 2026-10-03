"""TICKET-011：B-4 的检索半边 —— 按 trace_id / Skill 名 / 时间范围 / 是否降级检索。

`GET /traces` 的过滤与分页必须同时可在内存替身（无数据库的回放断言）与持久化
仓储（B-5）上运行；两条实现共享同一份 `TraceQuery` / `TraceSummary` 契约。
"""

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from repositories.trace import TraceRepository
from skills.trace import (
    InMemoryTraceSink,
    RouteDecision,
    SkippedSkill,
    Span,
    TraceQuery,
    TraceReader,
    TraceSink,
    new_trace_id,
)

SERVER_ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 10, 3, 10, 0, tzinfo=UTC)


def _span(trace_id: str, name: str, at: datetime, detail: dict | None = None) -> Span:
    return Span(
        trace_id=trace_id,
        name=name,
        status="ok",
        duration_ms=3,
        input_digest="in",
        output_digest="out",
        started_at=at,
        detail=detail,
    )


async def _record(
    sink,
    trace_id: str,
    at: datetime,
    *,
    skills_run: list[str],
    degraded: list[str] | None = None,
    skipped: list[SkippedSkill] | None = None,
) -> None:
    await sink.record_route(
        RouteDecision(
            trace_id=trace_id,
            skills_run=skills_run,
            skills_skipped=skipped or [],
            decided_at=at,
        )
    )
    for name in skills_run:
        await sink.record_span(_span(trace_id, name, at))
    if degraded:
        await sink.record_span(
            _span(
                trace_id,
                "orchestration",
                at,
                detail={"skills_run": skills_run, "degraded": degraded},
            )
        )


async def test_the_in_memory_double_search_returns_matches_and_a_total():
    sink = InMemoryTraceSink()
    plain = new_trace_id()
    degraded = new_trace_id()
    await _record(
        sink, plain, T0, skills_run=["safety-gate", "symptom-normalization", "orchestration"]
    )
    await _record(
        sink,
        degraded,
        T0 + timedelta(minutes=5),
        skills_run=["safety-gate", "symptom-normalization", "graph-inference", "orchestration"],
        degraded=["graph"],
    )

    assert isinstance(sink, TraceReader)
    assert isinstance(sink, TraceSink)

    items, total = await sink.search(TraceQuery())
    assert total == 2
    assert [item.trace_id for item in items] == [plain, degraded]
    assert items[1].degraded == ["graph"]
    assert items[0].degraded == []
    assert items[0].span_count == 3


async def test_search_filters_by_trace_id_skill_time_and_degraded():
    sink = InMemoryTraceSink()
    early = new_trace_id()
    late = new_trace_id()
    await _record(sink, early, T0, skills_run=["safety-gate", "orchestration"])
    await _record(
        sink,
        late,
        T0 + timedelta(hours=3),
        skills_run=["safety-gate", "graph-inference", "orchestration"],
        degraded=["graph"],
    )

    by_id, _ = await sink.search(TraceQuery(trace_id=late))
    assert [item.trace_id for item in by_id] == [late]

    by_skill, _ = await sink.search(TraceQuery(skill="graph-inference"))
    assert [item.trace_id for item in by_skill] == [late]

    by_window, _ = await sink.search(
        TraceQuery(start=T0 + timedelta(hours=1), end=T0 + timedelta(hours=4))
    )
    assert [item.trace_id for item in by_window] == [late]

    by_degraded, _ = await sink.search(TraceQuery(degraded=True))
    assert [item.trace_id for item in by_degraded] == [late]

    by_healthy, _ = await sink.search(TraceQuery(degraded=False))
    assert [item.trace_id for item in by_healthy] == [early]


async def test_search_pages_but_the_total_is_the_unpaged_count():
    sink = InMemoryTraceSink()
    trace_ids = [new_trace_id() for _ in range(5)]
    for index, trace_id in enumerate(trace_ids):
        await _record(
            sink,
            trace_id,
            T0 + timedelta(minutes=index),
            skills_run=["orchestration"],
        )

    page, total = await sink.search(TraceQuery(limit=2, offset=2))

    assert total == 5
    assert [item.trace_id for item in page] == [trace_ids[2], trace_ids[3]]


async def test_repeated_search_for_one_trace_id_is_stable():
    sink = InMemoryTraceSink()
    trace_id = new_trace_id()
    await _record(
        sink, trace_id, T0, skills_run=["safety-gate", "orchestration"]
    )

    first, _ = await sink.search(TraceQuery(trace_id=trace_id))
    second, _ = await sink.search(TraceQuery(trace_id=trace_id))

    assert first == second


@pytest.fixture
def migrated_url(tmp_path) -> str:
    db_path = tmp_path / "search.db"
    config = Config(str(SERVER_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    command.upgrade(config, "head")
    return f"sqlite+aiosqlite:///{db_path}"


@pytest.fixture
async def session_factory(migrated_url):
    engine = create_async_engine(migrated_url)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def test_the_durable_reader_searches_the_same_way(session_factory):
    early = new_trace_id()
    late = new_trace_id()
    async with session_factory() as session:
        repository = TraceRepository(session)
        await _record(repository, early, T0, skills_run=["safety-gate", "orchestration"])
        await _record(
            repository,
            late,
            T0 + timedelta(hours=3),
            skills_run=["safety-gate", "graph-inference", "orchestration"],
            degraded=["graph"],
        )
        await session.commit()

    async with session_factory() as session:
        repository = TraceRepository(session)
        by_skill, total = await repository.search(TraceQuery(skill="graph-inference"))
        by_degraded, degraded_total = await repository.search(TraceQuery(degraded=True))
        by_window, _ = await repository.search(
            TraceQuery(start=T0, end=T0 + timedelta(hours=1))
        )

    assert total == 1
    assert [item.trace_id for item in by_skill] == [late]
    assert by_skill[0].degraded == ["graph"]
    assert degraded_total == 1
    assert [item.trace_id for item in by_degraded] == [late]
    assert [item.trace_id for item in by_window] == [early]


async def test_the_durable_reader_compares_time_bounds_by_instant(session_factory):
    """带偏移的时间范围按同一时刻比较，而不是按墙上时间字符串（SPEC.md 3.7）。"""
    trace = new_trace_id()
    async with session_factory() as session:
        await _record(TraceRepository(session), trace, T0, skills_run=["orchestration"])
        await session.commit()

    plus_eight = timezone(timedelta(hours=8))
    # 18:00+08:00 == 10:00 UTC：起点取到边界，命中。
    async with session_factory() as session:
        inside, inside_total = await TraceRepository(session).search(
            TraceQuery(
                start=T0.astimezone(plus_eight),
                end=(T0 + timedelta(minutes=1)).astimezone(plus_eight),
            )
        )
        after, after_total = await TraceRepository(session).search(
            TraceQuery(start=(T0 + timedelta(minutes=1)).astimezone(plus_eight))
        )

    assert inside_total == 1
    assert [item.trace_id for item in inside] == [trace]
    assert after_total == 0
