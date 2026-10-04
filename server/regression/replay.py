"""回放 + 指标计算（B-1 驱动的唯一入口，SPEC.md 4.4）。

由基线重建 `OrchestrationPorts`（三个 `Replay*` 端口按录制顺序作答），再跑一次
B-1，全程零外部 I/O。比对时丢弃随机 `trace_id` 与墙钟字段（ticket 023 §8），
其余按解析后的对象比较。`MetricsReport.latency` 取基线录制的每条 `duration_ms`，
这样同一基线重复回放的四项指标完全一致（AC-B-39）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from regression.metrics import (
    CaseOutcome,
    JudgePort,
    MetricsReport,
    build_report,
    path_of,
)
from regression.ports import ReplayGraphPort, ReplayLlmPort, ReplayRetrievalPort
from regression.schema import Baseline, BaselineCase
from skills.orchestration import ChatRequest, OrchestrationPorts, Orchestrator
from skills.trace import InMemoryTraceSink, degraded_branches

#: 身份 / 墙钟字段：每次运行必然不同，永不比较（ticket 023 §8）。
_DROPPED_FRAME_KEYS = ("trace_id",)
_DROPPED_DONE_KEYS = ("cost_time",)


@dataclass(frozen=True)
class CaseRun:
    outcome: CaseOutcome
    evidence_matched: bool


def _normalize_frames(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for frame in frames:
        clean = {
            key: value for key, value in frame.items() if key not in _DROPPED_FRAME_KEYS
        }
        if clean.get("type") == "done":
            clean = {
                key: value for key, value in clean.items() if key not in _DROPPED_DONE_KEYS
            }
        normalized.append(clean)
    return normalized


def _frame_of(frames: list[dict[str, Any]], frame_type: str) -> dict[str, Any] | None:
    return next((frame for frame in frames if frame.get("type") == frame_type), None)


def _context_of(case: BaselineCase) -> str:
    parts: list[str] = []
    for response in case.ports.get("retrieval", []):
        for hit in response:
            content = hit.get("content")
            if isinstance(content, str):
                parts.append(content)
    return "\n".join(parts)


async def replay_case(case: BaselineCase) -> CaseRun:
    """Rebuild one consult from its recording and reduce it to a `CaseOutcome`."""
    ports = OrchestrationPorts(
        graph=ReplayGraphPort(case.ports.get("graph", [])),
        retrieval=ReplayRetrievalPort(case.ports.get("retrieval", [])),
        llm=ReplayLlmPort(case.llm_chunks),
    )
    sink = InMemoryTraceSink()
    orchestrator = Orchestrator(ports, sink)
    request = ChatRequest(
        session_id=case.input.session_id,
        message=case.input.message,
        explicit_symptoms=case.input.explicit_symptoms or None,
    )
    frames = [
        frame
        async for frame in orchestrator.run(request, session_id=case.input.session_id)
    ]

    safety = _frame_of(frames, "safety")
    done = _frame_of(frames, "done")
    intercepted = safety is not None and safety.get("decision") == "intercept"
    # degraded 分组由 B-4 的 span 证据读出（ticket 023 §3），并与 `done` 帧互证。
    degraded = degraded_branches(sink.spans)
    done_degraded = list(done.get("degraded", [])) if done else []
    candidates = tuple(
        candidate["disease"] for candidate in (done or {}).get("graph", [])
    )
    baseline_done = _frame_of(case.frames, "done") or {}
    baseline_candidates = tuple(
        candidate["disease"] for candidate in baseline_done.get("graph", [])
    )
    answer = "".join(
        frame["content"] for frame in frames if frame.get("type") == "content"
    )

    outcome = CaseOutcome(
        case_id=case.id,
        red_flag=case.red_flag,
        intercepted=intercepted,
        candidates=candidates,
        baseline_candidates=baseline_candidates,
        answer=answer,
        context=_context_of(case),
        path=path_of(intercepted=intercepted, degraded=degraded),
        duration_ms=case.duration_ms,
        exemptions=tuple(case.exemptions),
    )

    route = sink.routes[0] if sink.routes else None
    route_matched = route is not None and (
        list(route.skills_run) == case.route.skills_run
        and [(skipped.skill, skipped.reason) for skipped in route.skills_skipped]
        == [(skipped.skill, skipped.reason) for skipped in case.route.skills_skipped]
    )
    spans_matched = sorted((span.name, span.status) for span in sink.spans) == sorted(
        (span["name"], span["status"]) for span in case.spans
    )
    degraded_matched = degraded == done_degraded
    frames_matched = _normalize_frames(frames) == _normalize_frames(case.frames)

    return CaseRun(
        outcome=outcome,
        evidence_matched=bool(
            route_matched and spans_matched and degraded_matched and frames_matched
        ),
    )


async def replay_case_set(baseline: Baseline) -> list[CaseRun]:
    return [await replay_case(case) for case in baseline.cases]


async def run_regression(
    baseline: Baseline, *, judge: JudgePort | None = None
) -> MetricsReport:
    runs = await replay_case_set(baseline)
    return await build_report(
        [run.outcome for run in runs],
        judge=judge,
        exempt_ids=baseline.exempt_divergences,
    )
