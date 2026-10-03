"""B-2: the symptom-normalization Skill, exercised at the `invoke(input) -> output`
seam plus the shared-vocabulary seam (`extract_symptoms` / `normalize_terms`).

Every case here is the executable form of a row in
`skills/symptom_normalization/SKILL.md` section 4. The Skill is pure computation:
no ports, no database, no LLM (SPEC.md 3.4 / 3.6).

The alias table below is copied from FUNCTIONAL_SPEC.md 5.1 and is the independent
source of truth the implementation is checked against — it is deliberately not
derived from the code under test.
"""

import re
from pathlib import Path

import pytest

from skills.ports import LlmPort
from skills.protocol import SkillContext
from skills.symptom_normalization import (
    STANDARD_SYMPTOMS,
    SYMPTOM_TERMS,
    SymptomNormalizationSkill,
    extract_symptoms,
    normalize_terms,
)
from skills.trace import InMemoryTraceSink, new_trace_id
from tests.doubles import ThrowingLlmPort

SERVER_ROOT = Path(__file__).resolve().parents[1]
SKILL_MD = SERVER_ROOT / "skills" / "symptom_normalization" / "SKILL.md"
VOCABULARY_MODULE = SERVER_ROOT / "skills" / "symptom_normalization" / "vocabulary.py"
ALIAS_ROW = re.compile(r"\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|")
SCAN_EXCLUDE = {".venv", "__pycache__", ".tmp", "tests", "migrations"}

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


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("头疼", ["头痛"]),
        ("肚子痛", ["腹痛"]),
        ("拉肚子", ["腹泻"]),
        ("嗓子痛", ["咽痛"]),
    ],
)
async def test_colloquial_symptoms_normalize_to_standard_names(context, message, expected):
    outcome = await SymptomNormalizationSkill().invoke({"message": message}, context)

    assert outcome.status == "ok"
    assert outcome.output.symptoms == expected


async def test_empty_input_is_rejected_not_silently_continued(context):
    outcome = await SymptomNormalizationSkill().invoke({"message": ""}, context)

    assert outcome.status == "invalid_input"
    assert outcome.output is None
    assert outcome.error
    assert [span.status for span in context.sink.spans] == ["error"]


async def test_symptoms_are_ordered_by_first_occurrence(context):
    outcome = await SymptomNormalizationSkill().invoke(
        {"message": "肚子痛，头疼"}, context
    )

    assert outcome.status == "ok"
    assert outcome.output.symptoms == ["腹痛", "头痛"]


async def test_duplicates_collapse_keeping_the_first_occurrence(context):
    outcome = await SymptomNormalizationSkill().invoke(
        {"message": "头疼，发烧，头胀"}, context
    )

    assert outcome.status == "ok"
    assert outcome.output.symptoms == ["头痛", "发热"]


async def test_alias_and_standard_word_merge_into_one_entry(context):
    outcome = await SymptomNormalizationSkill().invoke(
        {"message": "头疼和头痛，还有发烧"}, context
    )

    assert outcome.status == "ok"
    assert outcome.output.symptoms == ["头痛", "发热"]


async def test_negated_expressions_are_not_counted(context):
    outcome = await SymptomNormalizationSkill().invoke(
        {"message": "没有头疼，也不发烧，只是有点咳嗽"}, context
    )

    assert outcome.status == "ok"
    assert outcome.output.symptoms == ["咳嗽"]


async def test_negation_does_not_mask_an_unnegated_mention(context):
    outcome = await SymptomNormalizationSkill().invoke(
        {"message": "没有头疼，但是肚子痛"}, context
    )

    assert outcome.status == "ok"
    assert outcome.output.symptoms == ["腹痛"]


@pytest.mark.parametrize(("surface", "standard"), ALIAS_PAIRS)
async def test_chat_and_graph_chains_produce_the_same_standard_set(
    context, surface, standard
):
    # /chat/send chain: free text goes through the Skill.
    chat = await SymptomNormalizationSkill().invoke({"message": surface}, context)
    # /graph/infer chain: an explicit symptom list goes through the same vocabulary.
    graph = normalize_terms([surface])

    assert chat.status == "ok"
    assert chat.output.symptoms == graph == [standard]


async def test_chat_and_graph_chains_agree_on_a_multi_symptom_message(context):
    message = "我头疼肚子痛，还拉肚子"

    chat = await SymptomNormalizationSkill().invoke({"message": message}, context)

    assert chat.output.symptoms == ["头痛", "腹痛", "腹泻"]
    assert normalize_terms(["头疼", "肚子痛", "拉肚子"]) == ["头痛", "腹痛", "腹泻"]


def test_unknown_graph_terms_are_kept_verbatim():
    assert normalize_terms(["头痛", "牙痛"]) == ["头痛", "牙痛"]


async def test_skill_output_matches_the_chat_chain_function(context):
    message = "嗓子痛，还拉肚子"

    outcome = await SymptomNormalizationSkill().invoke({"message": message}, context)

    assert outcome.output.symptoms == extract_symptoms(message) == ["咽痛", "腹泻"]


async def test_same_input_is_identical_over_100_runs(context):
    skill = SymptomNormalizationSkill()
    message = "头疼发烧，还拉肚子，没有胸痛"

    results = [await skill.invoke({"message": message}, context) for _ in range(100)]

    first = results[0].output.symptoms
    assert first == ["头痛", "发热", "腹泻"]
    assert all(result.output.symptoms == first for result in results)


async def test_trace_digest_carries_the_normalized_symptoms(context):
    outcome = await SymptomNormalizationSkill().invoke(
        {"message": "头疼发烧三天了"}, context
    )

    assert outcome.status == "ok"
    span = context.sink.spans[0]
    assert span.name == "symptom-normalization"
    assert span.status == "ok"
    assert outcome.output.vocabulary_version in span.output_digest
    for symptom in outcome.output.symptoms:
        assert symptom in span.output_digest


async def test_runs_with_a_throwing_llm_port_in_scope(context):
    # B-3: symptom-normalization declares no ports, so a fake LLM that raises on any
    # call must not be reachable from it. Instantiating the port keeps that guarantee
    # explicit in the test (SPEC.md 4.1).
    llm = ThrowingLlmPort()
    assert isinstance(llm, LlmPort)
    assert vars(SymptomNormalizationSkill()) == {}

    outcome = await SymptomNormalizationSkill().invoke({"message": "胸口痛"}, context)

    assert outcome.status == "ok"
    assert outcome.output.symptoms == ["胸痛"]
    assert [span.name for span in context.sink.spans] == ["symptom-normalization"]


def test_every_alias_target_is_a_standard_symptom():
    assert {standard for _, standard in ALIAS_PAIRS} <= set(STANDARD_SYMPTOMS)


def test_skill_md_alias_table_matches_the_runtime_vocabulary():
    block = SKILL_MD.read_text(encoding="utf-8").split("### 1.3", 1)[1].split("### 1.4", 1)[0]
    documented = set(ALIAS_ROW.findall(block))
    runtime = {
        (surface, term.standard)
        for term in SYMPTOM_TERMS
        for surface in term.surfaces
        if surface != term.standard
    }

    assert documented == runtime


def _python_sources():
    for path in SERVER_ROOT.rglob("*.py"):
        if SCAN_EXCLUDE & set(path.parts):
            continue
        yield path


def test_the_vocabulary_is_the_only_symptom_and_alias_table():
    # A duplicated table would restate many of the 22 alias surfaces as exact string
    # literals in another module; incidental mentions (e.g. safety-gate's "胸口痛"
    # inside a longer red-flag phrase) never reach half the table.
    alias_keys = [surface for surface, _ in ALIAS_PAIRS]
    threshold = len(alias_keys) // 2

    tables = []
    for path in _python_sources():
        text = path.read_text(encoding="utf-8")
        exact = {
            key for key in alias_keys if f'"{key}"' in text or f"'{key}'" in text
        }
        if len(exact) >= threshold:
            tables.append(path)

    assert tables == [VOCABULARY_MODULE]
