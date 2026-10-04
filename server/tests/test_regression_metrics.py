"""AC-B-36/37/38: the four regression indicators, defined in one place.

`MetricsReport` is the only aggregation the replay path emits. Its field names
are frozen by SPEC.md 5.3, and the indicators by SPEC.md 3.8 — including the
three-way decomposition of the hallucination rate and the exclusive latency
grouping that AC-B-38 forbids merging.
"""

import pytest

from regression.metrics import (
    CaseOutcome,
    HallucinationReport,
    LatencyBucket,
    LatencyReport,
    MetricsReport,
    UnavailableJudgePort,
    build_report,
    compare_reports,
    latency_of,
    hallucination,
    path_of,
    percentile,
)


class StubJudge:
    """A deterministic judge: every assertion is judged by looking it up."""

    available = True

    def __init__(self, supported: set[str]) -> None:
        self.supported = supported

    async def judge(self, assertion: str, context: str) -> bool:
        return assertion in self.supported


# --- latency (AC-B-38) ------------------------------------------------------


def test_percentile_is_nearest_rank_and_reproducible():
    values = [10, 20, 30, 40]

    assert percentile(values, 0.50) == 20
    assert percentile(values, 0.95) == 40
    # Nearest rank, not interpolation: four samples, the 95th is the maximum.
    assert percentile([5], 0.95) == 5
    assert percentile([], 0.95) == 0


def test_latency_groups_by_path_and_never_merges_the_three_buckets():
    report = latency_of(
        [("intercepted", 8), ("degraded", 3), ("degraded", 5), ("llm", 40)]
    )

    assert isinstance(report, LatencyReport)
    assert report.intercepted == LatencyBucket(p50=8, p95=8)
    assert report.degraded == LatencyBucket(p50=3, p95=5)
    assert report.llm == LatencyBucket(p50=40, p95=40)


def test_path_priority_is_intercepted_then_degraded_then_llm():
    # Exclusive: a case counts once, and a degraded intercept is an intercept.
    assert path_of(intercepted=True, degraded=("graph",)) == "intercepted"
    assert path_of(intercepted=False, degraded=("graph",)) == "degraded"
    assert path_of(intercepted=False, degraded=()) == "llm"


# --- rates (AC-B-36) --------------------------------------------------------


def _outcome(**overrides) -> CaseOutcome:
    base = dict(
        case_id="c",
        red_flag=False,
        intercepted=False,
        candidates=(),
        baseline_candidates=(),
        answer="",
        context="",
        path="llm",
        duration_ms=1,
    )
    base.update(overrides)
    return CaseOutcome(**base)


async def test_redflag_intercept_and_false_positive_rates():
    outcomes = [
        _outcome(case_id="r1", red_flag=True, intercepted=True),
        _outcome(case_id="r2", red_flag=True, intercepted=True),
        _outcome(case_id="n1", red_flag=False, intercepted=False),
        _outcome(case_id="n2", red_flag=False, intercepted=False),
    ]

    report = await build_report(outcomes)

    assert report.redflag_intercept_rate == 1.0
    assert report.redflag_false_positive_rate == 0.0
    assert report.case_count == 4


async def test_intercept_rate_below_one_and_false_positive_are_surfaced():
    outcomes = [
        _outcome(case_id="r1", red_flag=True, intercepted=True),
        _outcome(case_id="r2", red_flag=True, intercepted=False),
        _outcome(case_id="n1", red_flag=False, intercepted=True),
        _outcome(case_id="n2", red_flag=False, intercepted=False),
    ]

    report = await build_report(outcomes)

    assert report.redflag_intercept_rate == 0.5
    assert report.redflag_false_positive_rate == 0.5


async def test_intercept_rate_is_vacuously_full_without_redflag_cases():
    report = await build_report([_outcome(case_id="n1")])

    assert report.redflag_intercept_rate == 1.0
    assert report.redflag_false_positive_rate == 0.0


async def test_diagnosis_drift_rate_compares_the_ordered_candidate_list():
    outcomes = [
        # same order -> no drift
        _outcome(case_id="same", candidates=("感冒", "偏头痛"), baseline_candidates=("感冒", "偏头痛")),
        # reordered -> drift (order is behaviour)
        _outcome(case_id="reorder", candidates=("偏头痛", "感冒"), baseline_candidates=("感冒", "偏头痛")),
        # unchanged empty -> no drift
        _outcome(case_id="empty"),
    ]

    report = await build_report(outcomes)

    assert report.diagnosis_drift_rate == pytest.approx(1 / 3)


async def test_report_has_the_frozen_shape():
    report = await build_report([_outcome()])

    body = report.model_dump()

    assert set(body) == {
        "redflag_intercept_rate",
        "redflag_false_positive_rate",
        "diagnosis_drift_rate",
        "hallucination",
        "latency",
        "case_count",
    }
    assert set(body["latency"]) == {"intercepted", "llm", "degraded"}
    assert set(body["latency"]["llm"]) == {"p50", "p95"}
    assert isinstance(report, MetricsReport)


# --- hallucination (AC-B-37) ------------------------------------------------


async def test_a_grounded_deterministic_assertion_is_not_a_hallucination():
    report = await hallucination("建议服用氨氯地平控制血压。", "高血压患者可使用氨氯地平。")

    assert isinstance(report, HallucinationReport)
    assert report.deterministic_ratio == 0.0
    assert report.total == 1
    assert report.judge_available is False


async def test_a_drug_name_absent_from_the_context_is_an_unsupported_assertion():
    report = await hallucination("建议服用二甲双胍。", "高血压患者应低盐饮食、规律服药。")

    assert report.deterministic_ratio == 1.0
    assert report.judged_ratio == 0.0
    assert report.total == 1


async def test_a_number_absent_from_the_context_is_a_deterministic_hallucination():
    report = await hallucination("血压应控制在 130 以下。", "请定期监测血压。")

    assert report.deterministic_ratio == 1.0
    assert report.total == 1


async def test_free_text_is_judged_only_when_a_judge_is_available():
    answer = "请注意多休息。"

    judged = await hallucination(answer, "多休息有助于恢复。", judge=StubJudge(set()))
    unavailable = await hallucination(answer, "多休息有助于恢复。", judge=UnavailableJudgePort())

    assert judged.judge_available is True
    assert judged.judged_ratio == 1.0
    assert judged.total == 1
    assert unavailable.judge_available is False
    assert unavailable.judged_ratio == 0.0
    assert unavailable.total == 0  # nothing was evaluated, so it is not "no hallucination"


async def test_judge_support_ratio_and_deterministic_share_one_denominator():
    report = await hallucination(
        "建议服用二甲双胍。请注意多休息。",
        "高血压患者应低盐饮食。",
        judge=StubJudge({"请注意多休息。"}),
    )

    # 2 evaluated: the deterministic one is unsupported, the judged one is supported.
    assert report.total == 2
    assert report.deterministic_ratio == 0.5
    assert report.judged_ratio == 0.0
    assert report.judge_available is True


async def test_empty_answer_has_no_assertions():
    report = await hallucination("", "任意上下文。")

    assert report.total == 0
    assert report.deterministic_ratio == 0.0
    assert report.judged_ratio == 0.0


async def test_compare_reports_returns_the_deltas():
    primary = await build_report(
        [_outcome(red_flag=True, intercepted=True, path="intercepted", duration_ms=10)]
    )
    other = await build_report(
        [_outcome(red_flag=True, intercepted=False, path="intercepted", duration_ms=4)]
    )

    delta = compare_reports(primary, other)

    assert delta["redflag_intercept_rate"] == 1.0
    assert delta["diagnosis_drift_rate"] == 0.0
    assert set(delta["latency"]) == {"intercepted", "llm", "degraded"}
    assert delta["latency"]["intercepted"]["p95"] == 6
