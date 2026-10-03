"""B-4: the trace seam. Every Skill call and every LLM call leaves exactly one
span; the sink records them and hands one consult's trace back by `trace_id`."""

import json
import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel

DIGEST_LIMIT = 200

SpanStatus = Literal["ok", "error", "cancelled"]


def new_trace_id() -> str:
    return uuid.uuid4().hex


def digest(value: Any, limit: int = DIGEST_LIMIT) -> str:
    """A bounded summary — full patient text and full model output never land in a span."""
    if value is None:
        return ""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


class Span(BaseModel):
    trace_id: str
    name: str
    status: SpanStatus
    duration_ms: int
    input_digest: str
    output_digest: str
    started_at: datetime


class SkippedSkill(BaseModel):
    skill: str
    reason: str


class RouteDecision(BaseModel):
    trace_id: str
    skills_run: list[str]
    skills_skipped: list[SkippedSkill]
    decided_at: datetime


class TraceSummary(BaseModel):
    """One consult, as an aggregate over a time window."""

    trace_id: str
    started_at: datetime
    span_count: int


@runtime_checkable
class TraceSink(Protocol):
    async def record_span(self, span: Span) -> None: ...

    async def record_route(self, decision: RouteDecision) -> None: ...


@runtime_checkable
class TraceReader(Protocol):
    """What TICKET-011's observability API and the replay assertion read back."""

    async def spans_for(self, trace_id: str) -> Sequence[Span]: ...

    async def route_for(self, trace_id: str) -> RouteDecision | None: ...

    async def traces_between(
        self, start: datetime, end: datetime
    ) -> Sequence[TraceSummary]: ...


class InMemoryTraceSink:
    """Test double from SPEC.md 4.1 (B-4): assert — and replay — what was written,
    without a database."""

    def __init__(self) -> None:
        self.spans: list[Span] = []
        self.routes: list[RouteDecision] = []

    async def record_span(self, span: Span) -> None:
        self.spans.append(span)

    async def record_route(self, decision: RouteDecision) -> None:
        self.routes.append(decision)

    async def spans_for(self, trace_id: str) -> list[Span]:
        return sorted(
            (span for span in self.spans if span.trace_id == trace_id),
            key=lambda span: span.started_at,
        )

    async def route_for(self, trace_id: str) -> RouteDecision | None:
        return next(
            (route for route in self.routes if route.trace_id == trace_id), None
        )

    async def traces_between(
        self, start: datetime, end: datetime
    ) -> list[TraceSummary]:
        decisions = [route for route in self.routes if start <= route.decided_at <= end]
        return [
            TraceSummary(
                trace_id=route.trace_id,
                started_at=route.decided_at,
                span_count=sum(1 for span in self.spans if span.trace_id == route.trace_id),
            )
            for route in sorted(decisions, key=lambda route: route.decided_at)
        ]
