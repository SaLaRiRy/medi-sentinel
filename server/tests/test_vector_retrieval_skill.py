"""B-2/B-3: the vector-retrieval Skill, exercised at the `invoke(input) -> output`
seam plus the pure post-processing seam (`to_references` / `snippet_of`).

Every case here is the executable form of a row in
`skills/vector_retrieval/SKILL.md` section 4. The Skill reaches the outside world
only through the injected `RetrievalPort` (SPEC.md 4.1 B-3); tests inject in-memory
fakes, so no database, graph store or vector index is ever started.
"""

from pathlib import Path

import pytest

from skills.ports import LlmPort
from skills.protocol import SkillContext
from skills.trace import InMemoryTraceSink, new_trace_id
from skills.vector_retrieval import (
    RETRIEVAL_TOP_K,
    SCHEMA_VERSION,
    SNIPPET_LENGTH,
    VectorRetrievalSkill,
    snippet_of,
    to_references,
)
from tests.doubles import HitsRetrievalPort, ThrowingLlmPort, ThrowingRetrievalPort

SKILL_MD = (
    Path(__file__).resolve().parents[1] / "skills" / "vector_retrieval" / "SKILL.md"
)


@pytest.fixture
def context() -> SkillContext:
    return SkillContext(trace_id=new_trace_id(), sink=InMemoryTraceSink())


def _hit(file_name: str, content: str, distance: float) -> dict:
    return {
        "content": content,
        "metadata": {"file_name": file_name},
        "distance": distance,
    }


async def test_references_carry_index_file_name_snippet_and_distance(context):
    port = HitsRetrievalPort(
        [
            _hit("高血压防治指南.md", "低盐饮食，规律服药。", 0.12),
            _hit("糖尿病健康管理.md", "控制总热量，规律运动。", 0.35),
        ]
    )
    skill = VectorRetrievalSkill(retrieval=port)

    outcome = await skill.invoke({"query": "高血压平时要注意什么"}, context)

    assert outcome.status == "ok"
    assert outcome.output.degraded is False
    references = outcome.output.references
    assert [reference.index for reference in references] == [1, 2]
    assert [reference.file_name for reference in references] == [
        "高血压防治指南.md",
        "糖尿病健康管理.md",
    ]
    assert [reference.distance for reference in references] == [0.12, 0.35]
    assert [reference.snippet for reference in references] == [
        "低盐饮食，规律服药。",
        "控制总热量，规律运动。",
    ]
    assert port.calls == [("高血压平时要注意什么", 5)]


async def test_unavailable_index_degrades_without_raising(context):
    skill = VectorRetrievalSkill(retrieval=ThrowingRetrievalPort())

    outcome = await skill.invoke({"query": "高血压平时要注意什么"}, context)

    assert outcome.status == "ok"
    assert outcome.output.degraded is True
    assert outcome.output.degraded_reason
    assert outcome.output.references == []


async def test_malformed_hit_degrades_instead_of_raising(context):
    # 端口返回结构非法（缺 metadata.file_name）时走同一条降级路径，不阻断问答。
    port = HitsRetrievalPort([{"content": "正文", "distance": 0.1}])
    skill = VectorRetrievalSkill(retrieval=port)

    outcome = await skill.invoke({"query": "高血压"}, context)

    assert outcome.status == "ok"
    assert outcome.output.degraded is True
    assert outcome.output.references == []


async def test_snippet_is_the_first_200_characters(context):
    content = "高血压患者应低盐饮食。" * 40
    port = HitsRetrievalPort([_hit("高血压防治指南.md", content, 0.12)])

    outcome = await VectorRetrievalSkill(retrieval=port).invoke(
        {"query": "高血压"}, context
    )

    snippet = outcome.output.references[0].snippet
    assert len(content) > SNIPPET_LENGTH
    assert len(snippet) == SNIPPET_LENGTH
    assert snippet == content[:SNIPPET_LENGTH]


async def test_reference_carries_the_whole_chunk_for_prompt_context(context):
    # 引用项给 wire 契约前 200 字符，同时保留整块正文供编排拼提示词
    # （FUNCTIONAL_SPEC 5.3：context 片段是「[文档N] <整块正文>」）。
    content = "高血压患者应低盐饮食。" * 40
    port = HitsRetrievalPort([_hit("高血压防治指南.md", content, 0.12)])

    outcome = await VectorRetrievalSkill(retrieval=port).invoke(
        {"query": "高血压"}, context
    )

    reference = outcome.output.references[0]
    assert reference.snippet == content[:SNIPPET_LENGTH]
    assert reference.context == content


async def test_no_hits_is_ok_with_empty_references(context):
    port = HitsRetrievalPort([])

    outcome = await VectorRetrievalSkill(retrieval=port).invoke(
        {"query": "高血压"}, context
    )

    assert outcome.status == "ok"
    assert outcome.output.references == []
    assert outcome.output.degraded is False


async def test_a_far_hit_is_kept_because_there_is_no_threshold(context):
    # 无最低命中阈值（SPEC.md 附：Skill 清单）：距离 0.99 的命中也照常返回。
    port = HitsRetrievalPort([_hit("高血压防治指南.md", "低盐饮食。", 0.99)])

    outcome = await VectorRetrievalSkill(retrieval=port).invoke(
        {"query": "高血压"}, context
    )

    assert [reference.distance for reference in outcome.output.references] == [0.99]


async def test_hits_beyond_top_k_are_truncated_with_contiguous_indices(context):
    hits = [
        _hit(f"文档{position}.md", f"片段 {position}", position / 100)
        for position in range(1, RETRIEVAL_TOP_K + 4)
    ]
    port = HitsRetrievalPort(hits)

    outcome = await VectorRetrievalSkill(retrieval=port).invoke(
        {"query": "高血压"}, context
    )

    references = outcome.output.references
    assert len(references) == RETRIEVAL_TOP_K
    assert [reference.index for reference in references] == [1, 2, 3, 4, 5]
    assert [reference.file_name for reference in references] == [
        f"文档{position}.md" for position in range(1, RETRIEVAL_TOP_K + 1)
    ]


async def test_trace_digest_records_the_truncation_rule(context):
    port = HitsRetrievalPort([_hit("高血压防治指南.md", "低盐饮食。", 0.12)])

    outcome = await VectorRetrievalSkill(retrieval=port).invoke(
        {"query": "高血压"}, context
    )

    assert outcome.status == "ok"
    span = context.sink.spans[0]
    assert span.name == "vector-retrieval"
    assert span.status == "ok"
    assert f"top_k={RETRIEVAL_TOP_K}" in span.output_digest
    assert f"snippet_length={SNIPPET_LENGTH}" in span.output_digest


async def test_empty_input_is_rejected_not_silently_continued(context):
    skill = VectorRetrievalSkill(retrieval=HitsRetrievalPort())

    outcome = await skill.invoke({"query": ""}, context)

    assert outcome.status == "invalid_input"
    assert outcome.output is None
    assert outcome.error
    assert [span.status for span in context.sink.spans] == ["error"]


async def test_retrieval_does_not_call_the_llm_port(context):
    # 嵌入模型调用发生在 RetrievalPort 之内，不是大模型生成调用：即使环境中存在
    # 一个大模型端口，本 Skill 只用检索端口就能运行，且大模型从未被调用（SPEC.md 3.4）。
    llm = ThrowingLlmPort()
    assert isinstance(llm, LlmPort)
    port = HitsRetrievalPort([_hit("高血压防治指南.md", "低盐饮食。", 0.12)])
    skill = VectorRetrievalSkill(retrieval=port)

    # 本 Skill 的唯一外部协作方是检索端口：它不持有任何大模型端口。
    assert not any(isinstance(value, LlmPort) for value in vars(skill).values())

    outcome = await skill.invoke({"query": "高血压"}, context)

    assert outcome.status == "ok"
    assert [span.name for span in context.sink.spans] == ["vector-retrieval"]


async def test_to_references_matches_the_skill_output(context):
    hits = [
        _hit("高血压防治指南.md", "低盐饮食。", 0.12),
        _hit("糖尿病健康管理.md", "控制总热量。", 0.35),
    ]

    outcome = await VectorRetrievalSkill(retrieval=HitsRetrievalPort(hits)).invoke(
        {"query": "高血压"}, context
    )

    assert outcome.output.references == to_references(hits)
    assert outcome.output.references[0].snippet == snippet_of("低盐饮食。")


async def test_same_input_is_identical_over_100_runs(context):
    hits = [
        _hit("高血压防治指南.md", "低盐饮食。", 0.12),
        _hit("糖尿病健康管理.md", "控制总热量。", 0.35),
    ]
    skill = VectorRetrievalSkill(retrieval=HitsRetrievalPort(hits))

    results = [
        await skill.invoke({"query": "高血压平时要注意什么"}, context)
        for _ in range(100)
    ]

    first = results[0].output.references
    assert all(result.output.references == first for result in results)
    assert all(result.output.degraded is False for result in results)


def test_skill_md_documents_the_runtime_constants():
    text = SKILL_MD.read_text(encoding="utf-8")

    assert SCHEMA_VERSION in text
    assert "`RETRIEVAL_TOP_K`" in text and str(RETRIEVAL_TOP_K) in text
    assert "`SNIPPET_LENGTH`" in text and str(SNIPPET_LENGTH) in text
