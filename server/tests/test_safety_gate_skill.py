"""B-2: the safety-gate Skill, exercised at the `invoke(input) -> output` seam.

Every case here is the executable form of a row in
`skills/safety_gate/SKILL.md` section 4. The Skill is pure computation: no ports,
no database, no LLM (SPEC.md 3.4 / 3.5).
"""

import re
from pathlib import Path

import pytest

from skills.ports import LlmPort
from skills.protocol import SkillContext
from skills.safety_gate import RULES, RULES_VERSION, SafetyGateSkill
from skills.trace import InMemoryTraceSink, new_trace_id
from tests.doubles import ThrowingLlmPort

SKILL_MD = Path(__file__).resolve().parents[1] / "skills" / "safety_gate" / "SKILL.md"
RULE_ROW = re.compile(r"\|\s*\d+\s*\|\s*`([a-z0-9-]+)`\s*\|\s*`(urgent|critical)`\s*\|")


@pytest.fixture
def context() -> SkillContext:
    return SkillContext(trace_id=new_trace_id(), sink=InMemoryTraceSink())


async def test_plain_description_is_allowed(context):
    outcome = await SafetyGateSkill().invoke(
        {"message": "我头疼发烧三天了，吃了退烧药也没好转"}, context
    )

    assert outcome.status == "ok"
    assert outcome.output.decision == "allow"
    assert outcome.output.red_flags == []
    assert outcome.output.level is None
    assert outcome.output.message == ""
    assert outcome.output.suggested_action == ""
    assert outcome.output.rule_version == RULES_VERSION


async def test_emergency_description_is_intercepted(context):
    outcome = await SafetyGateSkill().invoke(
        {"message": "胸口剧痛，出冷汗，喘不上气"}, context
    )

    assert outcome.status == "ok"
    output = outcome.output
    assert output.decision == "intercept"
    assert output.level == "critical"
    assert {flag.id for flag in output.red_flags} == {"chest-pain", "dyspnea"}
    assert output.message
    assert output.suggested_action


async def test_negated_red_flags_do_not_intercept(context):
    outcome = await SafetyGateSkill().invoke(
        {"message": "没有胸痛，也不发烧，就是有点咳嗽"}, context
    )

    assert outcome.status == "ok"
    assert outcome.output.decision == "allow"
    assert outcome.output.red_flags == []


async def test_negated_hit_does_not_mask_an_unnegated_one(context):
    outcome = await SafetyGateSkill().invoke(
        {"message": "没有胸痛，但是喘不上气"}, context
    )

    assert outcome.status == "ok"
    assert outcome.output.decision == "intercept"
    assert [flag.id for flag in outcome.output.red_flags] == ["dyspnea"]


async def test_multiple_hits_return_all_and_take_the_highest_level(context):
    outcome = await SafetyGateSkill().invoke({"message": "剧烈头痛，还吐血"}, context)

    assert outcome.status == "ok"
    output = outcome.output
    assert output.decision == "intercept"
    assert [flag.id for flag in output.red_flags] == [
        "severe-headache",
        "severe-bleeding",
    ]
    assert [flag.level for flag in output.red_flags] == ["urgent", "critical"]
    assert output.level == "critical"
    assert output.suggested_action == "立即拨打 120 或前往最近的急诊科就诊。"


async def test_same_input_is_identical_over_100_runs(context):
    skill = SafetyGateSkill()
    message = "胸口剧痛，出冷汗，喘不上气，还一侧手脚没力气"

    results = [
        await skill.invoke({"message": message}, context) for _ in range(100)
    ]

    first = results[0].output
    assert first.decision == "intercept"
    assert all(result.output.decision == first.decision for result in results)
    assert all(result.output.red_flags == first.red_flags for result in results)


async def test_trace_digest_carries_the_red_flag_audit_trail(context):
    long_message = "患者：从前天起就不太舒服。" + "胸口剧痛，喘不上气，" + "很担心。" * 300

    outcome = await SafetyGateSkill().invoke({"message": long_message}, context)

    assert outcome.status == "ok"
    span = context.sink.spans[0]
    assert span.name == "safety-gate"
    assert span.status == "ok"
    assert RULES_VERSION in span.output_digest
    for flag in outcome.output.red_flags:
        assert flag.id in span.output_digest
        assert flag.matched_text in span.output_digest


async def test_empty_input_is_rejected_not_silently_continued(context):
    outcome = await SafetyGateSkill().invoke({"message": ""}, context)

    assert outcome.status == "invalid_input"
    assert outcome.output is None
    assert outcome.error
    assert [span.status for span in context.sink.spans] == ["error"]


async def test_runs_with_a_throwing_llm_port_in_scope(context):
    # B-3: safety-gate declares no ports, so an LLM fake that raises on any call
    # must not be reachable from it. Instantiating the port keeps that guarantee
    # explicit in the test (SPEC.md 4.1).
    llm = ThrowingLlmPort()
    assert isinstance(llm, LlmPort)
    assert vars(SafetyGateSkill()) == {}

    outcome = await SafetyGateSkill().invoke({"message": "胸口剧痛"}, context)

    assert outcome.status == "ok"
    assert outcome.output.decision == "intercept"
    assert [span.name for span in context.sink.spans] == ["safety-gate"]


def test_skill_md_rule_table_matches_the_runtime_rule_table():
    documented = set(RULE_ROW.findall(SKILL_MD.read_text(encoding="utf-8")))

    assert documented == {(rule.id, rule.level) for rule in RULES}
