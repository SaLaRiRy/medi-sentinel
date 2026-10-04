"""AC-B-34/39/40: the committed, version-controlled case set and baseline.

`cases/v1.json` is the versioned input set (SPEC.md 3.8), `baselines/v1.json` the
recorded baseline that ships with it. Replaying the committed baseline must be
clean: intercept 100%, false positive 0%, drift 0%, and the three latency buckets
all populated.
"""

from pathlib import Path

import pytest

from regression.schema import default_store
from regression.replay import run_regression

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def case_set():
    return default_store().load_case_set("v1")


@pytest.fixture(scope="module")
def baseline():
    return default_store().load_baseline("v1")


def test_case_set_v1_has_the_twenty_designed_cases(case_set):
    assert case_set.version == "v1"
    assert len(case_set.cases) == 20
    groups = [case.group for case in case_set.cases]
    assert groups.count("red_flag") == 6
    assert groups.count("llm") == 8
    assert groups.count("degraded") == 4
    assert groups.count("boundary") == 2


def test_case_set_covers_the_required_red_flag_families(case_set):
    messages = {case.message for case in case_set.cases if case.group == "red_flag"}

    # 胸痛+出冷汗+呼吸困难、大出血、意识障碍、剧烈头痛+呕吐、严重过敏（高热伴皮疹）、抽搐
    assert "胸口剧痛，出冷汗，喘不上气" in messages
    assert any("大量出血" in message for message in messages)
    assert any("意识不清" in message for message in messages)
    assert any("剧烈头痛" in message for message in messages)
    assert any("皮疹" in message for message in messages)
    assert any("抽搐" in message for message in messages)


def test_case_set_covers_the_colloquial_aliases(case_set):
    messages = [case.message for case in case_set.cases]

    assert {"我头疼", "肚子痛", "拉肚子", "嗓子痛"} <= set(messages)


async def test_the_committed_baseline_replays_clean(baseline):
    report = await run_regression(baseline)

    assert report.redflag_intercept_rate == 1.0
    assert report.redflag_false_positive_rate == 0.0
    assert report.diagnosis_drift_rate == 0.0
    assert report.case_count == 20
    # All three latency paths carry cases, and they are not merged.
    assert report.latency.intercepted.p95 > 0
    assert report.latency.degraded.p95 > 0
    assert report.latency.llm.p95 > 0


async def test_the_committed_baseline_reports_the_three_hallucination_fields(baseline):
    report = await run_regression(baseline)

    hallucination = report.hallucination
    assert hallucination.total > 0
    assert hallucination.deterministic_ratio == 0.0
    assert hallucination.judged_ratio == 0.0
    assert hallucination.judge_available is False


async def test_the_committed_baseline_is_reproducible(baseline):
    first = await run_regression(baseline)
    second = await run_regression(baseline)

    assert first.model_dump() == second.model_dump()


def test_case_set_and_baseline_are_tracked_in_version_control():
    assert (REPO_ROOT / "server/regression/cases/v1.json").is_file()
    assert (REPO_ROOT / "server/regression/baselines/v1.json").is_file()
    ignored = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "regression/baselines" not in ignored
