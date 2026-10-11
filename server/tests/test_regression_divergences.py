"""Intentional-divergence registry: 023 exempts `ai-chain`, records the other two.

The registry (`.scratch/medisentinel/intentional-divergences.md`) is the single
source of truth. 023 reads it read-only: the `ai-chain` subset (A-1…A-7) is
exempted from the drift / hallucination denominators, and the `http-contract`
subset (H-1…H-12) is recorded but never consumed here (024's input).

`stack` (S-*) carries the framework-level refactors that are neither a legacy
behaviour fix nor an HTTP-contract change. It is **only** recorded: reading it
into the exemption list would widen the drift / hallucination denominator and
blind the gate to the very change it is supposed to watch.
"""

from regression.divergences import (
    ai_chain_ids,
    http_contract_ids,
    load_registry,
    stack_ids,
)
from regression.metrics import CaseOutcome, build_report
from regression.schema import default_store


def test_registry_parses_the_two_scoped_subsets():
    registry = load_registry()

    assert ai_chain_ids(registry) == [f"A-{index}" for index in range(1, 9)]
    assert http_contract_ids(registry) == [f"H-{index}" for index in range(1, 15)]


def test_registry_parses_the_stack_subset_without_exempting_it():
    """`stack` 只登记：既不进豁免集，也不进 024 的消费集。"""
    registry = load_registry()

    assert stack_ids(registry) == [f"S-{index}" for index in range(1, 5)]
    assert set(stack_ids(registry)).isdisjoint(ai_chain_ids(registry))
    assert set(stack_ids(registry)).isdisjoint(http_contract_ids(registry))


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
