"""AC-B-33/34/35/39/40: record once, replay deterministically.

The framework's whole value is that a committed baseline re-runs a consult with
zero external I/O and reproduces itself exactly. These tests drive the package
functions (the CLI and the HTTP job are thin shells over them).
"""

import ast
import json
from pathlib import Path

import regression.ports as regression_ports
from regression.metrics import MetricsReport
from regression.record import record_case_set
from regression.replay import replay_case_set, run_regression
from regression.schema import CaseSet, RegressionCase


def _case(case_id: str, message: str, **overrides) -> RegressionCase:
    base = dict(
        id=case_id,
        group="llm",
        message=message,
        session_id=1000,
        answer=["建议多休息、多饮水。"],
    )
    base.update(overrides)
    return RegressionCase(**base)


def _case_set(*cases: RegressionCase) -> CaseSet:
    return CaseSet(version="test", cases=list(cases))


async def test_recorded_baseline_carries_inputs_skills_frames_and_duration():
    case_set = _case_set(_case("c1", "我头疼发烧三天了"))

    baseline = await record_case_set(case_set)

    assert baseline.version == case_set.version
    assert baseline.case_set_version == case_set.version
    recorded = baseline.cases[0]
    assert recorded.id == "c1"
    assert recorded.input.message == "我头疼发烧三天了"
    assert recorded.input.session_id == 1000
    assert recorded.red_flag is False
    assert recorded.duration_ms >= 0
    # 各 Skill 输出：安全门、归一化、检索、图谱、编排
    assert set(recorded.skills) == {
        "safety-gate",
        "symptom-normalization",
        "vector-retrieval",
        "graph-inference",
        "orchestration",
    }
    assert recorded.skills["symptom-normalization"]["symptoms"] == ["头痛", "发热"]
    # 全部 SSE 帧 + route + ports + llm chunks + spans
    assert [frame["type"] for frame in recorded.frames][:3] == [
        "session",
        "trace",
        "route",
    ]
    assert recorded.route.skills_run[0] == "safety-gate"
    assert recorded.ports["retrieval"], "the retrieval branch was recorded"
    assert recorded.ports["graph"], "the graph branch was recorded"
    assert recorded.llm_chunks == [["建议多休息、多饮水。"]]
    assert {span["name"] for span in recorded.spans} >= {"llm", "orchestration"}
    assert recorded.answer == "建议多休息、多饮水。"


async def test_replay_of_an_unchanged_baseline_reproduces_it_exactly():
    baseline = await record_case_set(_case_set(_case("c1", "我头疼发烧三天了")))

    runs = await replay_case_set(baseline)

    assert len(runs) == 1
    assert runs[0].evidence_matched is True


async def test_two_replays_of_the_same_baseline_produce_identical_metrics():
    baseline = await record_case_set(
        _case_set(
            _case("r1", "胸口剧痛，出冷汗，喘不上气", group="red_flag"),
            _case("n1", "我头疼"),
        )
    )

    first = await run_regression(baseline)
    second = await run_regression(baseline)

    assert isinstance(first, MetricsReport)
    assert first.model_dump() == second.model_dump()


async def test_redflag_intercept_rate_is_full_and_false_positive_is_zero():
    baseline = await record_case_set(
        _case_set(
            _case("r1", "胸口剧痛，出冷汗，喘不上气", group="red_flag"),
            _case("r2", "突然大量出血，止都止不住", group="red_flag"),
            _case("n1", "我头疼"),
            _case("n2", "拉肚子"),
        )
    )

    report = await run_regression(baseline)

    assert report.redflag_intercept_rate == 1.0
    assert report.redflag_false_positive_rate == 0.0


async def test_diagnosis_drift_is_zero_when_the_code_is_unchanged():
    baseline = await record_case_set(
        _case_set(_case("c1", "我头疼发烧三天了"), _case("c2", "我拉肚子"))
    )

    report = await run_regression(baseline)

    assert report.diagnosis_drift_rate == 0.0


async def test_latency_is_grouped_by_the_recorded_paths_never_merged():
    baseline = await record_case_set(
        _case_set(
            _case("r1", "胸口剧痛，出冷汗，喘不上气", group="red_flag"),
            _case("d1", "我头疼发烧", group="degraded", graph="unavailable"),
            _case("n1", "我头疼"),
        )
    )
    # The replay reads latency from the baseline's recorded durations (AC-B-39),
    # so pinning them proves the three buckets never merge.
    for case, duration in zip(baseline.cases, (11, 22, 33)):
        case.duration_ms = duration

    report = await run_regression(baseline)

    assert report.latency.intercepted.p95 == 11
    assert report.latency.degraded.p95 == 22
    assert report.latency.llm.p95 == 33


async def test_a_degraded_baseline_case_replays_as_degraded():
    baseline = await record_case_set(
        _case_set(
            _case("d1", "我头疼发烧", group="degraded", graph="unavailable"),
            _case("d2", "我拉肚子", group="degraded", retrieval="unavailable"),
        )
    )

    runs = await replay_case_set(baseline)
    report = await run_regression(baseline)

    assert runs[0].outcome.path == "degraded"
    assert runs[0].outcome.candidates == ()
    assert runs[1].outcome.path == "degraded"
    assert report.latency.llm.p95 == 0


async def test_baseline_json_round_trips():
    baseline = await record_case_set(_case_set(_case("c1", "我头疼")))

    payload = baseline.model_dump_json()
    restored = type(baseline).model_validate_json(payload)

    assert restored.case_set_version == baseline.case_set_version
    assert len(restored.cases) == 1
    assert json.loads(payload)["cases"][0]["input"]["message"] == "我头疼"


def test_replay_ports_never_import_a_real_adapter():
    source = Path(regression_ports.__file__).read_text(encoding="utf-8")
    modules: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules.append(node.module or "")

    forbidden = {"adapters", "neo4j", "chroma"}
    assert not [module for module in modules if module.split(".")[0] in forbidden]
