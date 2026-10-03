"""B-4 + B-5: the durable trace sink. It writes spans and route decisions into
the session's structured storage, and reads one consult's trace back out.

The session owns the transaction (B-5): nothing here commits, so a request's
spans land or roll back with everything else it wrote.
"""

from datetime import UTC, datetime

from sqlalchemy import select

from models.trace import RouteDecisionRow, TraceSpanRow
from repositories.base import Repository
from skills.trace import (
    RouteDecision,
    SkippedSkill,
    Span,
    TraceQuery,
    TraceSummary,
    page_of,
    summarize,
)


# SQLite stores and hands back naive `DateTime` values; the seam speaks UTC-aware
# datetimes (the in-memory double and every caller do). Normalize on the way out,
# and normalize a query's time bounds on the way in so a non-UTC offset still
# compares by instant rather than by wall-clock string.
def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class TraceRepository(Repository):
    """Implements both halves of the trace seam — `TraceSink` and `TraceReader`."""

    async def record_span(self, span: Span) -> None:
        self._session.add(
            TraceSpanRow(
                trace_id=span.trace_id,
                name=span.name,
                status=span.status,
                duration_ms=span.duration_ms,
                input_digest=span.input_digest,
                output_digest=span.output_digest,
                detail=span.detail,
                started_at=span.started_at,
            )
        )

    async def record_route(self, decision: RouteDecision) -> None:
        self._session.add(
            RouteDecisionRow(
                trace_id=decision.trace_id,
                skills_run=decision.skills_run,
                skills_skipped=[
                    skipped.model_dump() for skipped in decision.skills_skipped
                ],
                decided_at=decision.decided_at,
            )
        )

    async def spans_for(self, trace_id: str) -> list[Span]:
        rows = (
            (
                await self._session.execute(
                    select(TraceSpanRow)
                    .where(TraceSpanRow.trace_id == trace_id)
                    .order_by(TraceSpanRow.started_at, TraceSpanRow.id)
                )
            )
            .scalars()
            .all()
        )
        return [_to_span(row) for row in rows]

    async def route_for(self, trace_id: str) -> RouteDecision | None:
        row = (
            await self._session.execute(
                select(RouteDecisionRow).where(RouteDecisionRow.trace_id == trace_id)
            )
        ).scalar_one_or_none()
        return None if row is None else _to_decision(row)

    async def traces_between(
        self, start: datetime, end: datetime
    ) -> list[TraceSummary]:
        rows = (
            (
                await self._session.execute(
                    select(RouteDecisionRow)
                    .where(
                        RouteDecisionRow.decided_at >= start,
                        RouteDecisionRow.decided_at <= end,
                    )
                    .order_by(RouteDecisionRow.decided_at)
                )
            )
            .scalars()
            .all()
        )
        return [
            summarize(
                row.trace_id,
                _utc(row.decided_at),
                row.skills_run,
                await self.spans_for(row.trace_id),
            )
            for row in rows
        ]

    async def search(self, query: TraceQuery) -> tuple[list[TraceSummary], int]:
        statement = select(RouteDecisionRow)
        if query.trace_id is not None:
            statement = statement.where(RouteDecisionRow.trace_id == query.trace_id)
        if query.start is not None:
            statement = statement.where(RouteDecisionRow.decided_at >= _utc(query.start))
        if query.end is not None:
            statement = statement.where(RouteDecisionRow.decided_at <= _utc(query.end))
        rows = (await self._session.execute(statement)).scalars().all()
        summaries = [
            summarize(
                row.trace_id,
                _utc(row.decided_at),
                row.skills_run,
                await self.spans_for(row.trace_id),
            )
            for row in rows
        ]
        return page_of(summaries, query)


def _to_span(row: TraceSpanRow) -> Span:
    return Span(
        trace_id=row.trace_id,
        name=row.name,
        status=row.status,
        duration_ms=row.duration_ms,
        input_digest=row.input_digest,
        output_digest=row.output_digest,
        detail=row.detail,
        started_at=_utc(row.started_at),
    )


def _to_decision(row: RouteDecisionRow) -> RouteDecision:
    return RouteDecision(
        trace_id=row.trace_id,
        skills_run=list(row.skills_run),
        skills_skipped=[SkippedSkill(**item) for item in row.skills_skipped],
        decided_at=_utc(row.decided_at),
    )
