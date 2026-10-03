"""B-4 + B-5: the durable sink writes one consult's trace to structured storage,
then reads it back — keyed by `trace_id`, and aggregated over a time window.

Storage is built with `alembic upgrade head`, so this reaches the seam the way
production does, without asserting table structure (SPEC.md 4.1 B-4/B-5).
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from repositories.trace import TraceRepository
from skills.trace import (
    DIGEST_LIMIT,
    RouteDecision,
    SkippedSkill,
    Span,
    TraceReader,
    TraceSink,
    digest,
    new_trace_id,
)

SERVER_ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 10, 3, 10, 0, tzinfo=UTC)


def _span(trace_id: str, name: str, at: datetime, status: str = "ok") -> Span:
    return Span(
        trace_id=trace_id,
        name=name,
        status=status,
        duration_ms=3,
        input_digest="in",
        output_digest="out",
        started_at=at,
    )


def _decision(
    trace_id: str, at: datetime, skipped: list[SkippedSkill] | None = None
) -> RouteDecision:
    return RouteDecision(
        trace_id=trace_id,
        skills_run=["safety-gate", "symptom-normalization"],
        skills_skipped=skipped or [],
        decided_at=at,
    )


@pytest.fixture
def migrated_url(tmp_path) -> str:
    db_path = tmp_path / "trace.db"
    config = Config(str(SERVER_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    command.upgrade(config, "head")
    return f"sqlite+aiosqlite:///{db_path}"


@pytest.fixture
async def session_factory(migrated_url):
    engine = create_async_engine(migrated_url)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def test_trace_repository_is_the_durable_sink_and_reader(session_factory):
    async with session_factory() as session:
        repository = TraceRepository(session)

        assert isinstance(repository, TraceSink)
        assert isinstance(repository, TraceReader)


async def test_spans_survive_the_session_and_come_back_in_time_order(session_factory):
    trace = new_trace_id()
    other = new_trace_id()

    async with session_factory() as session:
        repository = TraceRepository(session)
        await repository.record_span(_span(trace, "safety-gate", T0 + timedelta(seconds=2)))
        await repository.record_span(_span(other, "safety-gate", T0))
        await repository.record_span(
            _span(trace, "symptom-normalization", T0 + timedelta(seconds=1))
        )
        await session.commit()

    async with session_factory() as session:
        spans = await TraceRepository(session).spans_for(trace)

    assert [span.name for span in spans] == ["symptom-normalization", "safety-gate"]
    assert all(span.trace_id == trace for span in spans)


async def test_route_decision_is_persisted_and_read_back_by_trace_id(session_factory):
    trace = new_trace_id()
    decision = _decision(
        trace, T0, [SkippedSkill(skill="graph-inference", reason="归一化输出为空")]
    )

    async with session_factory() as session:
        await TraceRepository(session).record_route(decision)
        await session.commit()

    async with session_factory() as session:
        repository = TraceRepository(session)
        stored = await repository.route_for(trace)
        assert await repository.route_for(new_trace_id()) is None

    assert stored is not None
    assert stored.skills_run == ["safety-gate", "symptom-normalization"]
    assert stored.skills_skipped == [
        SkippedSkill(skill="graph-inference", reason="归一化输出为空")
    ]


async def test_traces_are_aggregated_over_a_time_window(session_factory):
    early = new_trace_id()
    late = new_trace_id()

    async with session_factory() as session:
        repository = TraceRepository(session)
        await repository.record_route(_decision(early, T0))
        await repository.record_route(_decision(late, T0 + timedelta(hours=2)))
        await repository.record_span(_span(early, "safety-gate", T0))
        await repository.record_span(
            _span(early, "symptom-normalization", T0 + timedelta(milliseconds=5))
        )
        await repository.record_span(_span(late, "safety-gate", T0 + timedelta(hours=2)))
        await session.commit()

    window = (T0 - timedelta(minutes=1), T0 + timedelta(hours=1))
    async with session_factory() as session:
        summaries = await TraceRepository(session).traces_between(*window)

    assert [summary.trace_id for summary in summaries] == [early]
    assert summaries[0].span_count == 2


async def test_persisted_digests_stay_bounded(session_factory):
    trace = new_trace_id()
    patient_text = "患者主诉：" + "胸痛出冷汗喘不上气" * 200

    async with session_factory() as session:
        await TraceRepository(session).record_span(
            Span(
                trace_id=trace,
                name="orchestration",
                status="ok",
                duration_ms=5,
                input_digest=digest(patient_text),
                output_digest=digest(patient_text),
                started_at=T0,
            )
        )
        await session.commit()

    async with session_factory() as session:
        span = (await TraceRepository(session).spans_for(trace))[0]

    assert len(span.input_digest) <= DIGEST_LIMIT
    assert len(span.output_digest) <= DIGEST_LIMIT
    assert patient_text not in span.input_digest
    assert patient_text not in span.output_digest
