"""B-2: the single way anything runs a Skill — validate in, validate out, record one span."""

import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from skills.trace import Span, TraceSink, digest

OutcomeStatus = Literal["ok", "invalid_input", "failed"]


@dataclass(frozen=True)
class SkillContext:
    trace_id: str
    sink: TraceSink


@dataclass(frozen=True)
class SkillOutcome:
    status: OutcomeStatus
    output: BaseModel | None = None
    error: str | None = None


class Skill:
    """Deterministic runtime component (SPEC.md 3.4): no Skill but `orchestration`
    may call an LLM."""

    name: str = ""
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]

    async def run(self, data: BaseModel) -> BaseModel:
        raise NotImplementedError

    async def invoke(self, payload: Mapping[str, Any], context: SkillContext) -> SkillOutcome:
        started = time.perf_counter()
        started_at = datetime.now(UTC)
        payload_digest = digest(dict(payload))

        try:
            request = self.input_schema.model_validate(dict(payload))
        except ValidationError as error:
            await self._record(context, started, started_at, "error", payload_digest, "")
            return SkillOutcome(status="invalid_input", error=str(error))

        try:
            result = await self.run(request)
            response = self.output_schema.model_validate(result)
        except Exception as error:
            await self._record(context, started, started_at, "error", payload_digest, "")
            return SkillOutcome(
                status="failed", error=f"{type(error).__name__}: {error}"
            )

        await self._record(
            context, started, started_at, "ok", payload_digest, digest(response)
        )
        return SkillOutcome(status="ok", output=response)

    async def _record(
        self,
        context: SkillContext,
        started: float,
        started_at: datetime,
        status: Literal["ok", "error", "cancelled"],
        input_digest: str,
        output_digest: str,
    ) -> None:
        await context.sink.record_span(
            Span(
                trace_id=context.trace_id,
                name=self.name,
                status=status,
                duration_ms=int((time.perf_counter() - started) * 1000),
                input_digest=input_digest,
                output_digest=output_digest,
                started_at=started_at,
            )
        )
