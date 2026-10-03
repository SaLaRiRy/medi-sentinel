"""B-2 (unified invoke protocol with schema validation) and B-4 (one span per call)."""

import pytest
from pydantic import BaseModel

from skills.protocol import Skill, SkillContext
from skills.trace import DIGEST_LIMIT, InMemoryTraceSink, new_trace_id


class EchoInput(BaseModel):
    text: str


class EchoOutput(BaseModel):
    reply: str


class EchoSkill(Skill):
    name = "echo"
    input_schema = EchoInput
    output_schema = EchoOutput

    async def run(self, data: EchoInput) -> EchoOutput:
        return EchoOutput(reply=data.text.upper())


class ExplodingSkill(Skill):
    name = "exploding"
    input_schema = EchoInput
    output_schema = EchoOutput

    async def run(self, data: EchoInput) -> EchoOutput:
        raise RuntimeError("dependency unavailable")


@pytest.fixture
def context() -> SkillContext:
    return SkillContext(trace_id=new_trace_id(), sink=InMemoryTraceSink())


async def test_valid_input_returns_validated_output(context):
    outcome = await EchoSkill().invoke({"text": "hi"}, context)

    assert outcome.status == "ok"
    assert isinstance(outcome.output, EchoOutput)
    assert outcome.output.reply == "HI"


async def test_invalid_input_is_reported_instead_of_silently_continuing(context):
    outcome = await EchoSkill().invoke({"textt": "hi"}, context)

    assert outcome.status == "invalid_input"
    assert outcome.output is None
    assert outcome.error


async def test_every_invocation_records_exactly_one_span(context):
    await EchoSkill().invoke({"text": "hi"}, context)

    spans = context.sink.spans
    assert len(spans) == 1
    span = spans[0]
    assert span.name == "echo"
    assert span.trace_id == context.trace_id
    assert span.status == "ok"
    assert span.duration_ms >= 0
    assert span.input_digest
    assert span.output_digest


async def test_invalid_input_still_records_a_span(context):
    await EchoSkill().invoke({"textt": "hi"}, context)

    assert [span.status for span in context.sink.spans] == ["error"]


async def test_skill_failure_is_reported_and_recorded(context):
    outcome = await ExplodingSkill().invoke({"text": "hi"}, context)

    assert outcome.status == "failed"
    assert "dependency unavailable" in outcome.error
    assert [span.status for span in context.sink.spans] == ["error"]


async def test_digests_are_truncated_to_the_configured_limit(context):
    await EchoSkill().invoke({"text": "x" * 500}, context)

    span = context.sink.spans[0]
    assert len(span.input_digest) <= DIGEST_LIMIT
    assert len(span.output_digest) <= DIGEST_LIMIT
