"""B-1: the highest seam. Every end-to-end assertion and every regression metric
is computed on top of this entry point (SPEC.md 4.1).

One consult, in the order SPEC.md 2.3 fixes: trace id → safety gate first →
normalization → the two branches in parallel (they never filter each other) →
deterministic context assembly → the single LLM call → the SSE frames. A red flag
short-circuits the whole chain at the gate: no normalization, no branches, no
model (SPEC.md 3.5 / TICKET-008). This Skill is the only one allowed to call the
model (SPEC.md 3.4).

Degradation and failure are different outcomes (SPEC.md 5.2): the enhancement
branches may be unavailable without ending the consult — they degrade, the `done`
frame names them, and no error code is produced. Generation cannot degrade, so it
ends the stream with an `error` frame instead (TICKET-009).
"""

import asyncio
import time
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from skills.graph_inference import GraphInferenceOutput, GraphInferenceSkill
from skills.orchestration.frames import coverage_note, done_payload, safety_payload
from skills.orchestration.prompt import ChatTurn, build_context, build_prompt
from skills.ports import GraphPort, LlmPort, RetrievalPort
from skills.protocol import SkillContext, SkillOutcome
from skills.safety_gate import SafetyGateOutput, SafetyGateSkill
from skills.symptom_normalization import (
    SymptomNormalizationSkill,
    normalize_terms,
)
from skills.trace import RouteDecision, SkippedSkill, Span, TraceSink, digest, new_trace_id
from skills.vector_retrieval import VectorRetrievalOutput, VectorRetrievalSkill

SAFETY_GATE = "safety-gate"
SYMPTOM_NORMALIZATION = "symptom-normalization"
VECTOR_RETRIEVAL = "vector-retrieval"
GRAPH_INFERENCE = "graph-inference"
ORCHESTRATION = "orchestration"
LLM_SPAN = "llm"

GRAPH_SKIPPED_REASON = "安全门放行后未识别到任何标准症状（含显式症状），无可用图谱查询输入"
SAFETY_INTERCEPT_REASON = (
    "安全门拦截（红旗命中）：全链路短路，不执行归一化、检索、图谱与大模型"
)

# Generation failure codes (SPEC.md 5.2). Degraded branches produce no code at all.
LLM_UNAVAILABLE_CODE = 503
LLM_TIMEOUT_CODE = 504
INTERNAL_ERROR_CODE = 500


class LlmUnavailableError(RuntimeError):
    """Generation cannot degrade, so it ends the stream with an `error` frame.

    `code` is 503 when the model is unavailable and 504 when it times out; the
    message is always non-empty (SPEC.md 5.2 / 5.5).
    """

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _generation_failure(error: Exception) -> LlmUnavailableError:
    """Classify a raised model call: timeout → 504, anything else → 503.

    The deadline itself belongs to the adapter (SPEC.md 4.1 B-3); the `LlmPort`
    surfaces it as `TimeoutError`, which is also what `asyncio.timeout` raises.
    """
    if isinstance(error, TimeoutError):
        return LlmUnavailableError(LLM_TIMEOUT_CODE, f"生成超时：{type(error).__name__}")
    return LlmUnavailableError(LLM_UNAVAILABLE_CODE, f"生成失败：{type(error).__name__}")


class ChatRequest(BaseModel):
    session_id: int | None = None
    message: str = Field(min_length=1)
    explicit_symptoms: list[str] | None = None


@dataclass(frozen=True)
class OrchestrationPorts:
    graph: GraphPort
    retrieval: RetrievalPort
    llm: LlmPort


def _ordered_union(*groups: Sequence[str]) -> list[str]:
    """Concatenate symptom groups, keeping first-seen order and dropping repeats."""
    seen: set[str] = set()
    merged: list[str] = []
    for group in groups:
        for item in group:
            if item not in seen:
                seen.add(item)
                merged.append(item)
    return merged


class Orchestrator:
    def __init__(self, ports: OrchestrationPorts, sink: TraceSink) -> None:
        self._ports = ports
        self._sink = sink

    async def run(
        self,
        request: ChatRequest,
        *,
        session_id: int,
        history: Sequence[ChatTurn] = (),
    ) -> AsyncIterator[dict]:
        started = time.perf_counter()
        started_at = datetime.now(UTC)
        trace_id = new_trace_id()
        summary: dict = {}
        stream = self._run(
            request,
            session_id=session_id,
            history=history,
            trace_id=trace_id,
            started=started,
            summary=summary,
        )

        try:
            async for frame in stream:
                yield frame
        except LlmUnavailableError as error:
            await self._record_orchestration_span(
                trace_id, started, started_at, "error", request, session_id, summary
            )
            yield {
                "type": "error",
                "code": error.code,
                "message": error.message,
                "trace_id": trace_id,
            }
            return
        except Exception as error:
            # Anything that is not the model failing is an unexpected internal
            # failure, not an upstream outage (SPEC.md 5.2: 500 服务内部错误).
            await self._record_orchestration_span(
                trace_id, started, started_at, "error", request, session_id, summary
            )
            yield {
                "type": "error",
                "code": INTERNAL_ERROR_CODE,
                "message": f"内部错误：{type(error).__name__}",
                "trace_id": trace_id,
            }
            return
        finally:
            # A consumer that stops early (a hung-up client) closes this
            # generator, which would otherwise leave the inner generator parked on
            # its own yield — and the cancelled `llm` span unrecorded. Closing it
            # here settles the trace no matter which side of the yield the
            # cancellation landed on (SPEC.md 6.1 AC-B-26).
            await stream.aclose()

        # The intercept path short-circuits before orchestration runs as a Skill,
        # so it leaves no orchestration span — just the gate's (AC-E-02).
        if not summary.get("intercepted"):
            await self._record_orchestration_span(
                trace_id, started, started_at, "ok", request, session_id, summary
            )

    async def _run(
        self,
        request: ChatRequest,
        *,
        session_id: int,
        history: Sequence[ChatTurn],
        trace_id: str,
        started: float,
        summary: dict,
    ) -> AsyncIterator[dict]:
        context = SkillContext(trace_id=trace_id, sink=self._sink)

        yield {"type": "session", "session_id": session_id}
        yield {"type": "trace", "trace_id": trace_id}

        # ① 安全门 is first, before anything else and before any model call. It
        # reads the patient's own words only; `explicit_symptoms` cannot disarm
        # a process rule (SPEC.md 3.5 / TICKET-003 挂账第 4 条).
        safety = await SafetyGateSkill().invoke({"message": request.message}, context)
        if safety.output is None:
            raise RuntimeError(f"safety-gate did not return a decision: {safety.error}")
        if safety.output.decision == "intercept":
            async for frame in self._short_circuit(
                safety.output, trace_id=trace_id, started=started, summary=summary
            ):
                yield frame
            return

        # ② normalization over the raw text; the structured hint is normalized
        # through the same single vocabulary, never extracted separately.
        normalization = await SymptomNormalizationSkill().invoke(
            {"message": request.message}, context
        )
        message_symptoms = (
            list(normalization.output.symptoms) if normalization.output else []
        )
        explicit_symptoms = normalize_terms(request.explicit_symptoms or [])
        graph_symptoms = _ordered_union(message_symptoms, explicit_symptoms)

        skills_run = [SAFETY_GATE, SYMPTOM_NORMALIZATION, VECTOR_RETRIEVAL]
        skills_skipped: list[SkippedSkill] = []
        if graph_symptoms:
            skills_run.append(GRAPH_INFERENCE)
        else:
            skills_skipped.append(
                SkippedSkill(skill=GRAPH_INFERENCE, reason=GRAPH_SKIPPED_REASON)
            )
        skills_run.append(ORCHESTRATION)

        await self._sink.record_route(
            RouteDecision(
                trace_id=trace_id,
                skills_run=skills_run,
                skills_skipped=skills_skipped,
                decided_at=datetime.now(UTC),
            )
        )
        yield {
            "type": "route",
            "skills_run": skills_run,
            "skills_skipped": [skipped.model_dump() for skipped in skills_skipped],
        }
        summary["skills_run"] = skills_run
        summary["skills_skipped"] = [skipped.model_dump() for skipped in skills_skipped]

        # ③ the two branches, in parallel and independent: the retrieval branch
        # asks the raw question, the graph branch the standardized symptoms,
        # and neither one filters or re-ranks the other.
        calls = [
            VectorRetrievalSkill(self._ports.retrieval).invoke(
                {"query": request.message}, context
            )
        ]
        if graph_symptoms:
            calls.append(
                GraphInferenceSkill(self._ports.graph).invoke(
                    {"symptoms": graph_symptoms}, context
                )
            )
        outcomes = await asyncio.gather(*calls)

        retrieval = _output(VectorRetrievalOutput, outcomes[0])
        graph_result = (
            _output(GraphInferenceOutput, outcomes[1]) if graph_symptoms else None
        )
        references = list(retrieval.references) if retrieval else []
        candidates = list(graph_result.candidates) if graph_result else []

        degraded: list[str] = []
        if retrieval is None or retrieval.degraded:
            degraded.append("retrieval")
        # A branch whose Skill could not return a usable output counts as
        # degraded too; both branches are symmetric here (TICKET-009).
        if graph_symptoms and (graph_result is None or graph_result.degraded):
            degraded.append("graph")
        summary["references"] = len(references)
        summary["graph_candidates"] = len(candidates)
        summary["degraded"] = degraded

        # ④ deterministic context assembly.
        prompt = build_prompt(
            history=history,
            message=request.message,
            context=build_context(references, candidates),
        )

        # ⑤ the only model call, streamed straight onto the wire.
        llm_started = time.perf_counter()
        llm_started_at = datetime.now(UTC)
        answer: list[str] = []
        cancelled = False
        try:
            async for chunk in self._ports.llm.stream(prompt):
                if not chunk:
                    continue
                answer.append(chunk)
                yield {"type": "content", "content": chunk}
        except Exception as error:
            await self._record_span(
                trace_id, LLM_SPAN, "error", llm_started, llm_started_at,
                digest(prompt), "",
            )
            raise _generation_failure(error) from error
        except BaseException:
            # A client that hangs up cancels this task; the cancellation lands on
            # the downstream call, whose span must say `cancelled` rather than
            # vanish (SPEC.md 6.1 AC-B-26). CancelledError and GeneratorExit are
            # both BaseExceptions, so they need their own arm ahead of `finally`.
            cancelled = True
            raise
        else:
            await self._record_span(
                trace_id, LLM_SPAN, "ok", llm_started, llm_started_at,
                digest(prompt), digest("".join(answer)),
            )
        finally:
            if cancelled:
                await self._record_span(
                    trace_id, LLM_SPAN, "cancelled", llm_started, llm_started_at,
                    digest(prompt), digest("".join(answer)),
                )
        summary["answer_length"] = sum(len(chunk) for chunk in answer)

        yield done_payload(
            references=references,
            candidates=candidates,
            coverage_note=coverage_note(
                graph_skipped=not graph_symptoms, candidate_count=len(candidates)
            ),
            degraded=degraded,
            cost_time=int((time.perf_counter() - started) * 1000),
            trace_id=trace_id,
        )

    async def _short_circuit(
        self,
        safety: SafetyGateOutput,
        *,
        trace_id: str,
        started: float,
        summary: dict,
    ) -> AsyncIterator[dict]:
        """A red flag ends the consult before anything downstream of the gate runs.

        The route names only the gate, the trace keeps its single span, and the
        stream closes with an empty `done` — no model, no branches, no content
        (SPEC.md 3.5, 5.5 不变量 2, 6.3 AC-E-02).
        """
        skills_run = [SAFETY_GATE]
        skills_skipped = [
            SkippedSkill(skill=skill, reason=SAFETY_INTERCEPT_REASON)
            for skill in (
                SYMPTOM_NORMALIZATION,
                VECTOR_RETRIEVAL,
                GRAPH_INFERENCE,
                ORCHESTRATION,
            )
        ]
        await self._sink.record_route(
            RouteDecision(
                trace_id=trace_id,
                skills_run=skills_run,
                skills_skipped=skills_skipped,
                decided_at=datetime.now(UTC),
            )
        )
        # Signals `run` to skip the orchestration span: the gate's span is the only
        # one this turn leaves (SPEC.md 6.3 AC-E-02).
        summary["intercepted"] = True

        yield {
            "type": "route",
            "skills_run": skills_run,
            "skills_skipped": [skipped.model_dump() for skipped in skills_skipped],
        }
        yield safety_payload(safety)
        yield done_payload(
            references=[],
            candidates=[],
            coverage_note=None,
            degraded=[],
            cost_time=int((time.perf_counter() - started) * 1000),
            trace_id=trace_id,
        )

    async def _record_span(
        self,
        trace_id: str,
        name: str,
        status: str,
        started: float,
        started_at: datetime,
        input_digest: str,
        output_digest: str,
    ) -> None:
        await self._sink.record_span(
            Span(
                trace_id=trace_id,
                name=name,
                status=status,
                duration_ms=int((time.perf_counter() - started) * 1000),
                input_digest=input_digest,
                output_digest=output_digest,
                started_at=started_at,
            )
        )

    async def _record_orchestration_span(
        self,
        trace_id: str,
        started: float,
        started_at: datetime,
        status: str,
        request: ChatRequest,
        session_id: int,
        summary: dict,
    ) -> None:
        await self._record_span(
            trace_id,
            ORCHESTRATION,
            status,
            started,
            started_at,
            digest({"session_id": session_id, "message": request.message}),
            digest({"session_id": session_id, "status": status, **summary}),
        )


def _output(model: type[BaseModel], outcome: SkillOutcome) -> BaseModel | None:
    if outcome.status != "ok":
        return None
    if not isinstance(outcome.output, model):
        return None
    return outcome.output
