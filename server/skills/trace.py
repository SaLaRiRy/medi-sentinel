"""B-4: the trace sink. Every Skill call and every LLM call leaves exactly one span."""

import json
import uuid
from datetime import datetime
from typing import Any, Literal, Protocol

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


class TraceSink(Protocol):
    def record_span(self, span: Span) -> None: ...

    def record_route(self, decision: RouteDecision) -> None: ...


class InMemoryTraceSink:
    """Test double from SPEC.md 4.1 (B-4): assert what was written, without a database."""

    def __init__(self) -> None:
        self.spans: list[Span] = []
        self.routes: list[RouteDecision] = []

    def record_span(self, span: Span) -> None:
        self.spans.append(span)

    def record_route(self, decision: RouteDecision) -> None:
        self.routes.append(decision)
