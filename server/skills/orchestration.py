"""B-1: the highest seam. Every end-to-end assertion and every regression metric
is computed on top of this entry point.

For now the orchestrator emits the frame prefix and the closing frame, and records
the run's route decision (B-4). The safety gate, normalization, the two parallel
branches and generation arrive with TICKET-003..007; the frame contract they must
fill in is filed in `contracts/sse-events.json` (C-1).
"""

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from skills.ports import GraphPort, LlmPort, RetrievalPort
from skills.trace import RouteDecision, TraceSink, new_trace_id


class ChatRequest(BaseModel):
    session_id: int | None = None
    message: str = Field(min_length=1)
    explicit_symptoms: list[str] | None = None


@dataclass(frozen=True)
class OrchestrationPorts:
    graph: GraphPort
    retrieval: RetrievalPort
    llm: LlmPort


class Orchestrator:
    def __init__(self, ports: OrchestrationPorts, sink: TraceSink) -> None:
        self._ports = ports
        self._sink = sink

    async def run(
        self, request: ChatRequest, *, session_id: int
    ) -> AsyncIterator[dict]:
        started = time.perf_counter()
        trace_id = new_trace_id()

        yield {"type": "session", "session_id": session_id}
        yield {"type": "trace", "trace_id": trace_id}
        decision = RouteDecision(
            trace_id=trace_id,
            skills_run=[],
            skills_skipped=[],
            decided_at=datetime.now(UTC),
        )
        await self._sink.record_route(decision)
        yield {
            "type": "done",
            "references": [],
            "graph": [],
            "coverage_note": None,
            "degraded": [],
            "cost_time": int((time.perf_counter() - started) * 1000),
            "trace_id": trace_id,
        }
