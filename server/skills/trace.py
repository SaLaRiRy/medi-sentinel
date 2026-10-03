"""B-4: the trace seam. Every Skill call and every LLM call leaves exactly one
span; the sink records them and hands one consult's trace back by `trace_id`."""

import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

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
    # Structured, audit-relevant facts for this call (B-4, TICKET-011). Unlike the
    # two digests it is not clamped to `DIGEST_LIMIT`: when a message trips many
    # red flags or a query returns many references, the later entries' audit
    # fields survive here instead of being cut off mid-digest (003 挂账第 1 条).
    # It still must not carry raw patient text or full model output (SPEC.md 3.7).
    detail: dict[str, Any] | None = None


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
    #: The route's `skills_run`, so `GET /traces` can filter/report by skill.
    skills_run: list[str] = Field(default_factory=list)
    #: The `done.degraded` branches, so `GET /traces` can filter by degradation.
    degraded: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class TraceQuery:
    """The filters `GET /traces` exposes, expressed at the B-4 seam.

    `start` / `end` bound `decided_at` inclusively; `skill` matches any entry of
    `skills_run`; `degraded` matches whether the consult has any degraded branch.
    `limit` / `offset` page the ordered result; the total is always the unpaged
    match count.
    """

    trace_id: str | None = None
    skill: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    degraded: bool | None = None
    limit: int = 20
    offset: int = 0


#: Span name → the `done.degraded` branch name it degrades.
DEGRADED_BRANCH_NAMES: dict[str, str] = {
    "vector-retrieval": "retrieval",
    "graph-inference": "graph",
}


def degraded_branches(spans: Sequence[Span]) -> list[str]:
    """The degraded branches of one consult, read from its spans.

    The `orchestration` span's structured detail names them directly (it mirrors
    `done.degraded`); when the consult short-circuited before orchestration, the
    branch spans' own `degraded` flags are the fallback.
    """
    for span in spans:
        if span.name == "orchestration" and span.detail:
            degraded = span.detail.get("degraded")
            if isinstance(degraded, list) and all(
                isinstance(branch, str) for branch in degraded
            ):
                return list(degraded)
    branches: list[str] = []
    for span in spans:
        if span.detail and span.detail.get("degraded") is True:
            branch = DEGRADED_BRANCH_NAMES.get(span.name, span.name)
            if branch not in branches:
                branches.append(branch)
    return branches


def summarize(
    trace_id: str, decided_at: datetime, skills_run: Sequence[str], spans: Sequence[Span]
) -> TraceSummary:
    return TraceSummary(
        trace_id=trace_id,
        started_at=decided_at,
        span_count=len(spans),
        skills_run=list(skills_run),
        degraded=degraded_branches(spans),
    )


def matches_query(query: TraceQuery, summary: TraceSummary) -> bool:
    if query.trace_id is not None and summary.trace_id != query.trace_id:
        return False
    if query.skill is not None and query.skill not in summary.skills_run:
        return False
    if query.start is not None and summary.started_at < query.start:
        return False
    if query.end is not None and summary.started_at > query.end:
        return False
    if query.degraded is not None and bool(summary.degraded) != query.degraded:
        return False
    return True


def page_of(
    summaries: Sequence[TraceSummary], query: TraceQuery
) -> tuple[list[TraceSummary], int]:
    """Filter, order (deterministically) and page; return (page, unpaged total)."""
    matched = [summary for summary in summaries if matches_query(query, summary)]
    matched.sort(key=lambda summary: (summary.started_at, summary.trace_id))
    return matched[query.offset : query.offset + query.limit], len(matched)


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

    async def search(self, query: TraceQuery) -> tuple[Sequence[TraceSummary], int]: ...


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
            summarize(
                route.trace_id,
                route.decided_at,
                route.skills_run,
                [span for span in self.spans if span.trace_id == route.trace_id],
            )
            for route in sorted(decisions, key=lambda route: route.decided_at)
        ]

    async def search(self, query: TraceQuery) -> tuple[list[TraceSummary], int]:
        summaries = [
            summarize(
                route.trace_id,
                route.decided_at,
                route.skills_run,
                [span for span in self.spans if span.trace_id == route.trace_id],
            )
            for route in self.routes
        ]
        return page_of(summaries, query)
