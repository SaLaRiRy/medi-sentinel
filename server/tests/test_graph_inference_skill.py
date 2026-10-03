"""B-2/B-3: the graph-inference Skill, exercised at the `invoke(input) -> output`
seam, the pure inference seam (`coverage_of` / `normalize_department` /
`to_candidates`) and the injected `GraphPort`.

Every case here is the executable form of a row in
`skills/graph_inference/SKILL.md` section 4. The Skill reaches the outside world
only through the injected `GraphPort` (SPEC.md 4.1 B-3); tests inject in-memory
fakes, so no database, graph store or vector index is ever started.

The alias table below is copied from FUNCTIONAL_SPEC.md 5.1 as the independent
source of truth for the cross-chain case (chat chain `extract_symptoms` vs graph
chain `normalize_terms`), so AC-B-18 is checked at this Skill's public seam.
"""

import json
from pathlib import Path

import jsonschema
import pytest

from skills.graph_inference import (
    COVERAGE_DECIMALS,
    MAX_CANDIDATES,
    SCHEMA_VERSION,
    GraphInferenceSkill,
    coverage_of,
    normalize_department,
    to_candidates,
)
from skills.ports import LlmPort
from skills.protocol import SkillContext
from skills.symptom_normalization import extract_symptoms
from skills.trace import InMemoryTraceSink, new_trace_id
from tests.doubles import HitsGraphPort, ThrowingGraphPort, ThrowingLlmPort

SERVER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVER_ROOT.parent
SKILL_MD = SERVER_ROOT / "skills" / "graph_inference" / "SKILL.md"
SSE_CONTRACT = REPO_ROOT / "contracts" / "sse-events.json"

# FUNCTIONAL_SPEC.md 5.1: the 22 colloquial-surface → standard-symptom mappings.
ALIAS_PAIRS = (
    ("头疼", "头痛"),
    ("头胀", "头痛"),
    ("头昏", "头晕"),
    ("发烧", "发热"),
    ("发高烧", "发热"),
    ("高烧", "发热"),
    ("低烧", "发热"),
    ("肚子痛", "腹痛"),
    ("胃疼", "腹痛"),
    ("胸口闷", "胸闷"),
    ("疲倦", "乏力"),
    ("想吐", "恶心"),
    ("拉肚子", "腹泻"),
    ("关节疼", "关节痛"),
    ("腰疼", "腰痛"),
    ("看不清", "视力模糊"),
    ("流鼻涕", "流涕"),
    ("喉咙痛", "咽痛"),
    ("嗓子痛", "咽痛"),
    ("胸口痛", "胸痛"),
    ("没力气", "乏力"),
    ("疲劳", "乏力"),
)


@pytest.fixture
def context() -> SkillContext:
    return SkillContext(trace_id=new_trace_id(), sink=InMemoryTraceSink())


def _record(disease: str, matched: list[str], department: str | None = None) -> dict:
    return {"disease": disease, "matched_symptoms": matched, "department": department}


async def test_candidates_are_ranked_by_match_count_with_explicit_coverage(context):
    port = HitsGraphPort(
        [
            _record("上呼吸道感染", ["头痛", "发热"], "呼吸内科"),
            _record("偏头痛", ["头痛"], "神经内科"),
        ]
    )
    skill = GraphInferenceSkill(graph=port)

    outcome = await skill.invoke({"symptoms": ["头痛", "发热", "咳嗽"]}, context)

    assert outcome.status == "ok"
    assert outcome.output.symptoms == ["头痛", "发热", "咳嗽"]
    candidates = outcome.output.candidates
    assert [candidate.disease for candidate in candidates] == [
        "上呼吸道感染",
        "偏头痛",
    ]
    # Independent literals: 2/3 and 1/3, rounded to two decimals.
    assert [candidate.coverage for candidate in candidates] == [0.67, 0.33]
    assert [candidate.match_count for candidate in candidates] == [2, 1]


def test_coverage_is_rounded_to_two_decimals():
    assert coverage_of(1, 3) == 0.33
    assert coverage_of(2, 3) == 0.67
    assert coverage_of(1, 1) == 1.0
    assert coverage_of(0, 3) == 0.0


def test_coverage_rounds_half_up_not_bankers():
    # 1/8 = 0.125 与 5/8 = 0.625 是「四舍五入」与内置 round()（银行家舍入）
    # 会分歧的两个点（FUNCTIONAL_SPEC.md 5.3 要求四舍五入）。
    assert coverage_of(1, 8) == 0.13
    assert coverage_of(5, 8) == 0.63


async def test_missing_department_is_null_not_a_dash(context):
    port = HitsGraphPort(
        [
            _record("偏头痛", ["头痛"], None),
            _record("紧张性头痛", ["头痛"], "-"),
            _record("鼻窦炎", ["头痛"], "  耳鼻喉科  "),
        ]
    )

    outcome = await GraphInferenceSkill(graph=port).invoke({"symptoms": ["头痛"]}, context)

    departments = [candidate.department for candidate in outcome.output.candidates]
    assert departments == [None, None, "耳鼻喉科"]


def test_normalize_department_treats_missing_and_dash_as_null():
    assert normalize_department(None) is None
    assert normalize_department("-") is None
    assert normalize_department("  ") is None
    assert normalize_department(" 心内科 ") == "心内科"


async def test_matched_symptoms_are_the_input_symptoms_the_disease_explains(context):
    # 端口返回的命中症状按输入症状顺序落库，且只保留本次查询的症状集合。
    port = HitsGraphPort([_record("上呼吸道感染", ["发热", "头痛", "牙痛"])])

    outcome = await GraphInferenceSkill(graph=port).invoke(
        {"symptoms": ["头痛", "发热"]}, context
    )

    candidate = outcome.output.candidates[0]
    assert candidate.matched_symptoms == ["头痛", "发热"]
    assert candidate.match_count == 2
    assert candidate.coverage == 1.0


async def test_a_disease_matching_only_one_symptom_is_still_returned(context):
    # 无最低命中阈值（SPEC.md 附：Skill 清单）。
    port = HitsGraphPort([_record("偏头痛", ["头痛"], "神经内科")])

    outcome = await GraphInferenceSkill(graph=port).invoke(
        {"symptoms": ["头痛", "发热", "咳嗽", "乏力", "腹泻"]}, context
    )

    assert [candidate.coverage for candidate in outcome.output.candidates] == [0.2]


async def test_candidates_beyond_the_limit_are_truncated_not_silently(context):
    records = [
        _record(f"疾病{position:02d}", ["头痛"])
        for position in range(1, MAX_CANDIDATES + 3)
    ]
    port = HitsGraphPort(records)

    outcome = await GraphInferenceSkill(graph=port).invoke({"symptoms": ["头痛"]}, context)

    assert outcome.output.limit == MAX_CANDIDATES
    assert len(outcome.output.candidates) == MAX_CANDIDATES
    assert [candidate.disease for candidate in outcome.output.candidates] == [
        f"疾病{position:02d}" for position in range(1, MAX_CANDIDATES + 1)
    ]


async def test_trace_digest_records_the_truncation_rule(context):
    port = HitsGraphPort([_record("偏头痛", ["头痛"], "神经内科")])

    outcome = await GraphInferenceSkill(graph=port).invoke({"symptoms": ["头痛"]}, context)

    assert outcome.status == "ok"
    span = context.sink.spans[0]
    assert span.name == "graph-inference"
    assert span.status == "ok"
    assert f"limit={MAX_CANDIDATES}" in span.output_digest
    assert f"coverage_decimals={COVERAGE_DECIMALS}" in span.output_digest


async def test_unavailable_graph_degrades_without_raising(context):
    skill = GraphInferenceSkill(graph=ThrowingGraphPort())

    outcome = await skill.invoke({"symptoms": ["头痛", "发热"]}, context)

    assert outcome.status == "ok"
    assert outcome.output.degraded is True
    assert outcome.output.degraded_reason
    assert outcome.output.candidates == []
    assert outcome.output.symptoms == ["头痛", "发热"]


async def test_malformed_record_degrades_instead_of_raising(context):
    port = HitsGraphPort([{"disease": "偏头痛"}])  # 缺 matched_symptoms

    outcome = await GraphInferenceSkill(graph=port).invoke({"symptoms": ["头痛"]}, context)

    assert outcome.status == "ok"
    assert outcome.output.degraded is True
    assert outcome.output.candidates == []


async def test_empty_normalized_symptoms_skip_the_graph_query(context):
    # 「没有头痛」归一化后为空：直接返回空列表，不查询图数据库（FUNCTIONAL_SPEC 5.3）。
    port = HitsGraphPort([_record("偏头痛", ["头痛"], "神经内科")])

    outcome = await GraphInferenceSkill(graph=port).invoke(
        {"symptoms": ["没有头痛"]}, context
    )

    assert outcome.status == "ok"
    assert outcome.output.symptoms == []
    assert outcome.output.candidates == []
    assert outcome.output.degraded is False
    assert port.calls == []


async def test_unknown_symptoms_are_queried_verbatim(context):
    # normalize_terms 对词表外的词按原样保留（维持既有 /graph/infer 行为）。
    port = HitsGraphPort([_record("牙髓炎", ["牙痛"], "口腔科")])

    outcome = await GraphInferenceSkill(graph=port).invoke({"symptoms": ["牙痛"]}, context)

    assert outcome.output.symptoms == ["牙痛"]
    assert port.calls == [("牙痛",)]


async def test_empty_input_is_rejected_not_silently_continued(context):
    skill = GraphInferenceSkill(graph=HitsGraphPort())

    outcome = await skill.invoke({"symptoms": []}, context)

    assert outcome.status == "invalid_input"
    assert outcome.output is None
    assert outcome.error
    assert [span.status for span in context.sink.spans] == ["error"]


async def test_graph_inference_does_not_call_the_llm_port(context):
    llm = ThrowingLlmPort()
    assert isinstance(llm, LlmPort)
    port = HitsGraphPort([_record("偏头痛", ["头痛"], "神经内科")])
    skill = GraphInferenceSkill(graph=port)

    assert not any(isinstance(value, LlmPort) for value in vars(skill).values())

    outcome = await skill.invoke({"symptoms": ["头痛"]}, context)

    assert outcome.status == "ok"
    assert [span.name for span in context.sink.spans] == ["graph-inference"]


@pytest.mark.parametrize(("surface", "standard"), ALIAS_PAIRS)
async def test_chat_and_graph_chains_produce_the_same_standard_set(
    context, surface, standard
):
    # /chat/send chain: free text → standard symptoms.
    chat = extract_symptoms(surface)
    # /graph/infer chain: an explicit symptom list → the same standard symptoms,
    # consumed by this Skill through the shared vocabulary (SPEC.md 6.1 AC-B-18).
    port = HitsGraphPort()
    outcome = await GraphInferenceSkill(graph=port).invoke(
        {"symptoms": [surface]}, context
    )

    assert outcome.output.symptoms == chat == [standard]
    assert port.calls == [(standard,)]


async def test_same_input_is_identical_over_100_runs(context):
    port = HitsGraphPort(
        [
            _record("上呼吸道感染", ["头痛", "发热"], "呼吸内科"),
            _record("偏头痛", ["头痛"], "神经内科"),
        ]
    )
    skill = GraphInferenceSkill(graph=port)

    results = [
        await skill.invoke({"symptoms": ["头疼", "发烧"]}, context) for _ in range(100)
    ]

    first = results[0].output.candidates
    assert [candidate.disease for candidate in first] == ["上呼吸道感染", "偏头痛"]
    assert all(result.output.candidates == first for result in results)
    assert all(result.output.degraded is False for result in results)


def test_to_candidates_is_the_pure_projection_the_skill_uses():
    records = [
        _record("上呼吸道感染", ["头痛", "发热"], "呼吸内科"),
        _record("偏头痛", ["头痛"], "神经内科"),
    ]

    projected = [candidate.model_dump() for candidate in to_candidates(records, ["头痛", "发热"])]

    assert projected == [
        {
            "disease": "上呼吸道感染",
            "match_count": 2,
            "coverage": 1.0,
            "department": "呼吸内科",
            "matched_symptoms": ["头痛", "发热"],
        },
        {
            "disease": "偏头痛",
            "match_count": 1,
            "coverage": 0.5,
            "department": "神经内科",
            "matched_symptoms": ["头痛"],
        },
    ]


async def test_each_candidate_satisfies_the_sse_contract_schema(context):
    port = HitsGraphPort(
        [
            _record("上呼吸道感染", ["头痛", "发热"], "呼吸内科"),
            _record("偏头痛", ["头痛"], None),
        ]
    )

    outcome = await GraphInferenceSkill(graph=port).invoke(
        {"symptoms": ["头痛", "发热"]}, context
    )

    schema = json.loads(SSE_CONTRACT.read_text(encoding="utf-8"))
    candidate_schema = schema["$defs"]["disease_candidate"]
    for candidate in outcome.output.candidates:
        jsonschema.validate(candidate.model_dump(), candidate_schema)


def test_probability_does_not_exist_in_runtime_code_or_contracts():
    roots = [
        SERVER_ROOT / "skills",
        SERVER_ROOT / "api",
        SERVER_ROOT / "repositories",
        SERVER_ROOT / "models",
    ]
    sources = [
        path
        for root in roots
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    ]
    contracts = list((REPO_ROOT / "contracts").rglob("*.json"))

    offenders = [
        path
        for path in [*sources, *contracts]
        if "probability" in path.read_text(encoding="utf-8").lower()
    ]

    assert offenders == []


def test_skill_md_documents_the_runtime_constants():
    text = SKILL_MD.read_text(encoding="utf-8")

    assert SCHEMA_VERSION in text
    assert "`MAX_CANDIDATES`" in text and str(MAX_CANDIDATES) in text
    assert "`COVERAGE_DECIMALS`" in text and str(COVERAGE_DECIMALS) in text
    assert "coverage" in text
