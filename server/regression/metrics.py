"""`MetricsReport` and the four indicators, defined once (SPEC.md 3.8 / 5.3).

- 红旗拦截率 = 标记为红旗的用例中 `decision == intercept` 的比例（目标 100%）
- 误拦率     = 非红旗用例中被拦截的比例（目标 0%）
- 诊断漂移率 = 候选疾病**有序列表**与基线不一致的用例比例
- 幻觉率     = 无据断言 / 已评估断言，拆成 `deterministic_ratio` + `judged_ratio`
- P95 延迟   = 按 `intercepted` / `llm` / `degraded` **互斥**分组，不合并（AC-B-38）

The hallucination report splits the rate across the two evaluation layers on one
shared denominator (`total`, the number of evaluated assertions):
`deterministic_ratio` is the unsupported share found by vocabulary literal
matching, `judged_ratio` the unsupported share found by the judge model. When no
judge is available the judged layer is skipped — `judged_ratio = 0.0` and
`judge_available = false` — so the zero is never misread as "no hallucination".
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from graph.ontology import _NODES_BY_LABEL
from regression.ports import JudgePort, UnavailableJudgePort  # noqa: F401  (re-exported)

PathName = Literal["intercepted", "llm", "degraded"]

#: 确定性层依据的图谱词表：数值、药品名、疾病名、检查名（SPEC.md 3.8）。
_DETERMINISTIC_TERMS: tuple[str, ...] = tuple(
    name
    for label in ("Disease", "Drug", "Check")
    for name in _NODES_BY_LABEL[label]
)

_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_ASSERTION_SPLIT = re.compile(r"(?<=[。！？!?\n])")


class LatencyBucket(BaseModel):
    p50: int
    p95: int


class LatencyReport(BaseModel):
    """Three exclusive buckets; a case lands in exactly one (AC-B-38)."""

    intercepted: LatencyBucket
    llm: LatencyBucket
    degraded: LatencyBucket


class HallucinationReport(BaseModel):
    """幻觉率的两层分解。

    ⚠️ **AC-12 起注意分母的含义**：`total` 是**含可判定 token 的断言数**
    （即 `evaluable`），**不是**答案的全部非空断言。v3 实测全部断言 1267 条，
    其中只有 400 条（32%）可被这层判定；未评估的 867 条里大量是
    「就医 / 急诊 / 警惕」类安全提示。所以本报告的比率**不具备"幻觉率"的解释力**，
    只能读作「可判定断言中被字面层标记无据的占比」。
    覆盖率与全分母口径见 `MetricsReport.literal_marked_ratio` / `evaluable_ratio`。
    """

    deterministic_ratio: float
    judged_ratio: float
    total: int
    judge_available: bool


class MetricsReport(BaseModel):
    redflag_intercept_rate: float
    redflag_false_positive_rate: float
    diagnosis_drift_rate: float
    hallucination: HallucinationReport
    latency: LatencyReport
    case_count: int
    #: 回放自检：本次回放的帧 / 路由 / span 与录制**逐字一致**的用例比例。
    #: 它**不是第五个指标**（SPEC.md 3.8 的四项定义不变、不参与换模型对比阈值），
    #: 而是"这次回放本身有没有漂"的自检——票 03 修的就是它此前被丢掉、永远进不了报告。
    evidence_match_rate: float
    # —— TICKET-AC-12 第一步：把「覆盖率」当一等公民报出来（中性命名，不叫 hallucination）——
    #: 全部**非空断言**数（口径之间可比的那个分母）。
    assertion_count: int
    #: 其中含可判定 token、因而能被字面层评估的条数（= `hallucination.total`）。
    evaluable_count: int
    #: 不含任何可判定 token、因此**无法评估**的条数——v3 上大量是安全提示句。
    token_free_count: int
    #: `evaluable_count / assertion_count`（v3：≈0.32）。这条比任何比率都重要。
    evaluable_ratio: float
    #: 被字面层标记为无据的条数（不含判定层）。
    literal_marked_count: int
    #: `literal_marked_count / assertion_count` —— 分母固定为全部断言，
    #: **口径之间可直接比较**，是唯一建议对外报的单一数字（仍须标注"字面标记率，不是幻觉率"）。
    literal_marked_ratio: float


@dataclass(frozen=True)
class CaseOutcome:
    """One replayed case, reduced to what the indicators need."""

    case_id: str
    red_flag: bool
    intercepted: bool
    candidates: tuple[str, ...]
    baseline_candidates: tuple[str, ...]
    answer: str
    context: str
    path: PathName
    duration_ms: int
    #: 有意偏离登记册里、本次对比须豁免的 id（如 ai-chain A-1…A-7）。
    exemptions: tuple[str, ...] = ()
    #: 该用例的回放证据是否与录制一致（票 03 起进报告）。手工构造的用例默认视为一致；
    #: 真实回放（`regression/replay.py`）一定显式传入。
    evidence_matched: bool = True


def percentile(values: Sequence[int], quantile: float) -> int:
    """Nearest-rank percentile — deterministic, no interpolation."""
    if not values:
        return 0
    ordered = sorted(values)
    rank = math.ceil(quantile * len(ordered))
    index = min(max(rank, 1), len(ordered)) - 1
    return int(ordered[index])


def path_of(*, intercepted: bool, degraded: Sequence[str]) -> PathName:
    """Exclusive grouping, priority `intercepted` → `degraded` → `llm`."""
    if intercepted:
        return "intercepted"
    if degraded:
        return "degraded"
    return "llm"


def latency_of(rows: Sequence[tuple[PathName, int]]) -> LatencyReport:
    buckets: dict[PathName, list[int]] = {"intercepted": [], "llm": [], "degraded": []}
    for path, duration_ms in rows:
        buckets[path].append(duration_ms)
    return LatencyReport(
        **{
            path: LatencyBucket(
                p50=percentile(values, 0.50), p95=percentile(values, 0.95)
            )
            for path, values in buckets.items()
        }
    )


def _rate(matching: int, total: int) -> float:
    return matching / total if total else 0.0


def _assertions(answer: str) -> list[str]:
    return [
        segment.strip()
        for segment in _ASSERTION_SPLIT.split(answer)
        if segment.strip()
    ]


def _deterministic_tokens(assertion: str) -> list[str]:
    tokens = [term for term in _DETERMINISTIC_TERMS if term in assertion]
    tokens.extend(_NUMBER.findall(assertion))
    return list(dict.fromkeys(tokens))


@dataclass
class _Evaluation:
    deterministic_total: int = 0
    deterministic_unsupported: int = 0
    judged_total: int = 0
    judged_unsupported: int = 0
    judge_available: bool = False
    #: 不含任何可判定 token、两层都评估不了的断言数（TICKET-AC-12）。
    token_free: int = 0

    @property
    def total(self) -> int:
        return self.deterministic_total + self.judged_total


async def _evaluate(answer: str, context: str, judge: JudgePort | None) -> _Evaluation:
    result = _Evaluation(
        judge_available=judge is not None and getattr(judge, "available", True)
    )
    for assertion in _assertions(answer):
        tokens = _deterministic_tokens(assertion)
        if tokens:
            result.deterministic_total += 1
            if not all(token in context for token in tokens):
                result.deterministic_unsupported += 1
            continue
        if not result.judge_available or judge is None:
            # 字面层没有 token、判定层又不可用 → 这条断言**无法评估**。
            # 过去它被 `continue` 静默吞掉；现在记进 token_free，让覆盖率可见。
            result.token_free += 1
            continue
        try:
            supported = await judge.judge(assertion, context)
        except Exception:
            # A judge that dies mid-report degrades the judged layer rather than
            # failing the whole replay (SPEC.md 3.8「降级不阻断」).
            result.judge_available = False
            break
        result.judged_total += 1
        if not supported:
            result.judged_unsupported += 1
    return result


async def hallucination(
    answer: str, context: str, *, judge: JudgePort | None = None
) -> HallucinationReport:
    """The hallucination rate of one answer, split across the two layers."""
    result = await _evaluate(answer, context, judge)
    total = result.total
    return HallucinationReport(
        deterministic_ratio=_rate(result.deterministic_unsupported, total),
        judged_ratio=_rate(result.judged_unsupported, total),
        total=total,
        judge_available=result.judge_available,
    )


async def build_report(
    outcomes: Sequence[CaseOutcome],
    *,
    judge: JudgePort | None = None,
    exempt_ids: Sequence[str] = (),
) -> MetricsReport:
    """Aggregate every indicator over a replayed case set.

    Cases carrying an `exempt_ids` exemption (the intentional `ai-chain`
    divergences, ticket 023 registry rule) are left out of the drift and
    hallucination denominators, so a deliberate change is never counted as a
    regression. Interception is unaffected: the exempt subset never touches the
    safety gate.
    """
    exempt = set(exempt_ids)
    eligible = [outcome for outcome in outcomes if not (exempt & set(outcome.exemptions))]
    red_flags = [outcome for outcome in outcomes if outcome.red_flag]
    non_red_flags = [outcome for outcome in outcomes if not outcome.red_flag]
    drifted = sum(
        1
        for outcome in eligible
        if outcome.candidates != outcome.baseline_candidates
    )

    evaluation = _Evaluation(
        judge_available=judge is not None and getattr(judge, "available", True)
    )
    for outcome in eligible:
        case_eval = await _evaluate(outcome.answer, outcome.context, judge)
        evaluation.deterministic_total += case_eval.deterministic_total
        evaluation.deterministic_unsupported += case_eval.deterministic_unsupported
        evaluation.judged_total += case_eval.judged_total
        evaluation.judged_unsupported += case_eval.judged_unsupported
        evaluation.token_free += case_eval.token_free
        evaluation.judge_available = evaluation.judge_available and case_eval.judge_available
    total = evaluation.total
    assertion_count = total + evaluation.token_free

    return MetricsReport(
        # 无红旗用例时没有可能被漏拦的红旗：按 100% 报（空集真值），否则 CLI 会把
        # 一个不含红旗的用例集误判成阻断性失败。
        redflag_intercept_rate=(
            _rate(sum(1 for outcome in red_flags if outcome.intercepted), len(red_flags))
            if red_flags
            else 1.0
        ),
        redflag_false_positive_rate=_rate(
            sum(1 for outcome in non_red_flags if outcome.intercepted),
            len(non_red_flags),
        ),
        diagnosis_drift_rate=_rate(drifted, len(eligible)),
        hallucination=HallucinationReport(
            deterministic_ratio=_rate(evaluation.deterministic_unsupported, total),
            judged_ratio=_rate(evaluation.judged_unsupported, total),
            total=total,
            judge_available=evaluation.judge_available,
        ),
        latency=latency_of([(outcome.path, outcome.duration_ms) for outcome in outcomes]),
        case_count=len(outcomes),
        evidence_match_rate=_rate(
            sum(1 for outcome in outcomes if outcome.evidence_matched), len(outcomes)
        ),
        assertion_count=assertion_count,
        evaluable_count=total,
        token_free_count=evaluation.token_free,
        evaluable_ratio=_rate(total, assertion_count),
        literal_marked_count=evaluation.deterministic_unsupported,
        literal_marked_ratio=_rate(
            evaluation.deterministic_unsupported, assertion_count
        ),
    )


def compare_reports(primary: MetricsReport, baseline: MetricsReport) -> dict[str, object]:
    """The delta of one report against another (ticket 023 §7 换模型工作流).

    Latency deltas are P95 differences only: the trend the design cares about is
    「延迟变差了多少」, and the two reports' P95 are each baseline-recorded values.
    """
    return {
        "redflag_intercept_rate": (
            primary.redflag_intercept_rate - baseline.redflag_intercept_rate
        ),
        "redflag_false_positive_rate": (
            primary.redflag_false_positive_rate - baseline.redflag_false_positive_rate
        ),
        "diagnosis_drift_rate": (
            primary.diagnosis_drift_rate - baseline.diagnosis_drift_rate
        ),
        "hallucination": {
            "deterministic_ratio": (
                primary.hallucination.deterministic_ratio
                - baseline.hallucination.deterministic_ratio
            ),
            "judged_ratio": (
                primary.hallucination.judged_ratio
                - baseline.hallucination.judged_ratio
            ),
            "total": primary.hallucination.total - baseline.hallucination.total,
        },
        "latency": {
            path: {
                "p95": getattr(primary.latency, path).p95
                - getattr(baseline.latency, path).p95
            }
            for path in ("intercepted", "llm", "degraded")
        },
        "evidence_match_rate": (
            primary.evidence_match_rate - baseline.evidence_match_rate
        ),
        # AC-12：口径之间可比的单一数字，以及覆盖率。
        "literal_marked_ratio": (
            primary.literal_marked_ratio - baseline.literal_marked_ratio
        ),
        "evaluable_ratio": primary.evaluable_ratio - baseline.evaluable_ratio,
    }


__all__ = [
    "CaseOutcome",
    "HallucinationReport",
    "JudgePort",
    "LatencyBucket",
    "LatencyReport",
    "MetricsReport",
    "PathName",
    "UnavailableJudgePort",
    "build_report",
    "compare_reports",
    "hallucination",
    "latency_of",
    "path_of",
    "percentile",
]
