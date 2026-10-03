"""B-4: the trace seam records, then hands one consult's trace back by `trace_id`.

The in-memory double is the recording sink SPEC.md 4.1 names: it lets a test
assert what was written — and replay it — without a database.
"""

from datetime import UTC, datetime, timedelta

from skills.trace import (
    InMemoryTraceSink,
    RouteDecision,
    SkippedSkill,
    Span,
    TraceReader,
    TraceSink,
    new_trace_id,
)

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


def test_in_memory_sink_is_the_recording_double_of_the_trace_seam():
    sink = InMemoryTraceSink()

    assert isinstance(sink, TraceSink)
    assert isinstance(sink, TraceReader)


async def test_spans_come_back_by_trace_id_in_time_order():
    sink = InMemoryTraceSink()
    trace = new_trace_id()
    other = new_trace_id()

    await sink.record_span(_span(trace, "safety-gate", T0 + timedelta(seconds=2)))
    await sink.record_span(_span(other, "safety-gate", T0))
    await sink.record_span(_span(trace, "symptom-normalization", T0 + timedelta(seconds=1)))

    spans = await sink.spans_for(trace)

    assert [span.name for span in spans] == ["symptom-normalization", "safety-gate"]
    assert all(span.trace_id == trace for span in spans)


async def test_route_decision_comes_back_by_trace_id():
    sink = InMemoryTraceSink()
    trace = new_trace_id()
    decision = RouteDecision(
        trace_id=trace,
        skills_run=["safety-gate"],
        skills_skipped=[SkippedSkill(skill="graph-inference", reason="归一化输出为空")],
        decided_at=T0,
    )
    await sink.record_route(decision)

    assert await sink.route_for(trace) == decision
    assert await sink.route_for(new_trace_id()) is None
