"""Intentional-divergence registry: 023 exempts `ai-chain`, records `http-contract`.

The registry (`.scratch/medisentinel/intentional-divergences.md`) is the single
source of truth. 023 reads it read-only: the `ai-chain` subset (A-1…A-7) is
exempted from the drift / hallucination denominators, and the `http-contract`
subset (H-1…H-12) is recorded but never consumed here (024's input).
"""

from regression.divergences import (
    ai_chain_ids,
    http_contract_ids,
    load_registry,
)
from regression.metrics import CaseOutcome, build_report
from regression.schema import default_store


def test_registry_parses_the_two_scoped_subsets():
    registry = load_registry()

    assert ai_chain_ids(registry) == [f"A-{index}" for index in range(1, 8)]
    assert http_contract_ids(registry) == [f"H-{index}" for index in range(1, 13)]


def test_committed_baseline_embeds_both_divergence_lists():
    baseline = default_store().load_baseline("v1")

    assert baseline.exempt_divergences == [f"A-{index}" for index in range(1, 8)]
    assert baseline.recorded_divergences == [f"H-{index}" for index in range(1, 13)]
    # The recorded-only subset is never exempted: 023 does not consume http-contract.
    assert set(baseline.recorded_divergences).isdisjoint(baseline.exempt_divergences)


async def test_exempt_cases_are_left_out_of_drift_and_hallucination():
    base = dict(
        red_flag=False,
        intercepted=False,
        answer="",
        context="",
        path="llm",
        duration_ms=1,
    )
    outcomes = [
        CaseOutcome(
            case_id="stable",
            candidates=(),
            baseline_candidates=(),
            **base,
        ),
        CaseOutcome(
            case_id="intentional",
            candidates=("偏头痛",),
            baseline_candidates=("感冒",),
            exemptions=("A-1",),
            **base,
        ),
    ]

    without_exemption = await build_report(outcomes)
    with_exemption = await build_report(outcomes, exempt_ids=["A-1", "A-2"])

    # 1 of 2 cases drifted (the exempt one): counted only without the exemption.
    assert without_exemption.diagnosis_drift_rate == 0.5
    # Only the non-exempt case enters the denominator; it did not drift.
    assert with_exemption.diagnosis_drift_rate == 0.0
    assert with_exemption.case_count == 2
