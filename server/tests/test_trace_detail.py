"""TICKET-011（003 挂账第 1 条）：trace 除受限摘要外，还留一份结构化 `detail`。

问题：`output_digest` 有 200 字上限。一次输入命中多条红旗、或一次检索返回多条引用时，
摘要会在中途截断，后面条目的命中标识、匹配片段与规则版本全部丢失（`SPEC.md` 3.7、
6.1 AC-B-15 / AC-B-33）。

本票的决定：为 `Span` 增加结构化 `detail`（动 B-4 seam 与 B-5 存储）。
`detail` 不再受 200 字上限约束，但同样不得落患者原文与大模型完整输出（`SPEC.md` 3.7）。
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from repositories.trace import TraceRepository
from skills.graph_inference import GraphInferenceSkill
from skills.orchestration import ChatRequest, OrchestrationPorts, Orchestrator
from skills.protocol import SkillContext
from skills.safety_gate import RULES_VERSION, SafetyGateSkill
from skills.symptom_normalization import SymptomNormalizationSkill
from skills.trace import DIGEST_LIMIT, InMemoryTraceSink, Span, new_trace_id
from skills.vector_retrieval import VectorRetrievalSkill
from tests.doubles import (
    HitsGraphPort,
    HitsRetrievalPort,
    ScriptedLlmPort,
)

SERVER_ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 10, 3, 10, 0, tzinfo=UTC)

# 六条红旗按规则表顺序命中；JSON 表示远超 200 字，最后几条必然被摘要截断。
SIX_RED_FLAGS = "胸痛，喘不上气，剧烈头痛，一侧肢体无力，意识不清，吐血"
EXPECTED_RED_FLAG_IDS = [
    "chest-pain",
    "dyspnea",
    "severe-headache",
    "stroke",
    "altered-consciousness",
    "severe-bleeding",
]


def _context(sink: InMemoryTraceSink) -> SkillContext:
    return SkillContext(trace_id=new_trace_id(), sink=sink)


def test_span_detail_is_optional_and_defaults_to_none():
    span = Span(
        trace_id=new_trace_id(),
        name="safety-gate",
        status="ok",
        duration_ms=1,
        input_digest="in",
        output_digest="out",
        started_at=T0,
    )

    assert span.detail is None


async def test_the_b2_protocol_records_every_skills_structured_detail():
    sink = InMemoryTraceSink()
    context = _context(sink)
    retrieval = HitsRetrievalPort(
        [
            {
                "content": "发热期间应多饮水。" + "正文" * 100,
                "metadata": {"file_name": "感冒与流感指南.md"},
                "distance": 0.21,
            }
        ]
    )
    graph = HitsGraphPort(
        [{"disease": "感冒", "matched_symptoms": ["发热", "头痛"], "department": "呼吸内科"}]
    )

    await SafetyGateSkill().invoke({"message": "我头疼发烧三天了"}, context)
    await SymptomNormalizationSkill().invoke({"message": "我头疼发烧三天了"}, context)
    await VectorRetrievalSkill(retrieval).invoke({"query": "我头疼发烧三天了"}, context)
    await GraphInferenceSkill(graph).invoke({"symptoms": ["头痛", "发热"]}, context)

    details = {span.name: span.detail for span in sink.spans}
    assert details["safety-gate"] is not None
    assert details["symptom-normalization"] == {
        "vocabulary_version": "symptom-vocabulary-v1",
        "symptoms": ["头痛", "发热"],
    }
    assert details["vector-retrieval"]["references"][0]["file_name"] == "感冒与流感指南.md"
    assert details["graph-inference"]["candidates"][0]["disease"] == "感冒"


async def test_multi_red_flag_audit_survives_output_digest_truncation():
    """003 挂账第 1 条的核心断言：摘要截断后，审计三元组仍完整。"""
    sink = InMemoryTraceSink()

    outcome = await SafetyGateSkill().invoke({"message": SIX_RED_FLAGS}, _context(sink))

    assert outcome.status == "ok"
    span = sink.spans[0]
    # 摘要被截到上限……
    assert len(span.output_digest) <= DIGEST_LIMIT
    # ……最后一条红旗的标识确实没能进入摘要（这正是挂账描述的信息丢失）。
    assert "severe-bleeding" not in span.output_digest
    # 结构化 detail 保住了全部命中项与规则版本，无一丢失。
    assert span.detail is not None
    assert span.detail["rule_version"] == RULES_VERSION
    assert [flag["id"] for flag in span.detail["red_flags"]] == EXPECTED_RED_FLAG_IDS
    for flag in span.detail["red_flags"]:
        assert flag["matched_surface"]
        assert flag["severity"] in {"urgent", "emergency"}


async def test_multi_reference_audit_survives_output_digest_truncation():
    hits = [
        {
            "content": f"第{index}条正文。" + "正" * 200,
            "metadata": {"file_name": f"文档{index}.md"},
            "distance": round(index / 10, 2),
        }
        for index in range(1, 6)
    ]
    sink = InMemoryTraceSink()

    outcome = await VectorRetrievalSkill(HitsRetrievalPort(hits)).invoke(
        {"query": "我头疼发烧三天了"}, _context(sink)
    )

    assert outcome.status == "ok"
    span = sink.spans[0]
    assert len(span.output_digest) <= DIGEST_LIMIT
    assert "文档5.md" not in span.output_digest
    assert span.detail is not None
    assert [item["index"] for item in span.detail["references"]] == [1, 2, 3, 4, 5]
    assert [item["file_name"] for item in span.detail["references"]] == [
        "文档1.md",
        "文档2.md",
        "文档3.md",
        "文档4.md",
        "文档5.md",
    ]
    assert [item["distance"] for item in span.detail["references"]] == [
        0.1,
        0.2,
        0.3,
        0.4,
        0.5,
    ]


async def test_a_full_consult_leaves_structured_detail_on_every_span():
    ports = OrchestrationPorts(
        graph=HitsGraphPort(
            [{"disease": "感冒", "matched_symptoms": ["发热"], "department": None}]
        ),
        retrieval=HitsRetrievalPort(
            [{"content": "多饮水", "metadata": {"file_name": "指南.md"}, "distance": 0.3}]
        ),
        llm=ScriptedLlmPort(["好的"]),
    )
    sink = InMemoryTraceSink()

    async for _ in Orchestrator(ports=ports, sink=sink).run(
        ChatRequest(message="我头疼发烧三天了"), session_id=1
    ):
        pass

    assert {span.name for span in sink.spans} == {
        "safety-gate",
        "symptom-normalization",
        "vector-retrieval",
        "graph-inference",
        "orchestration",
        "llm",
    }
    for span in sink.spans:
        assert span.detail is not None, f"{span.name} has no structured detail"


async def test_the_trace_alone_reproduces_the_consults_replayable_facts():
    """AC-B-33：不访问任何端口，仅凭 trace 即可重建本次问诊的关键事实。"""
    ports = OrchestrationPorts(
        graph=HitsGraphPort(
            [{"disease": "感冒", "matched_symptoms": ["发热"], "department": "呼吸内科"}]
        ),
        retrieval=HitsRetrievalPort(
            [{"content": "多饮水", "metadata": {"file_name": "指南.md"}, "distance": 0.3}]
        ),
        llm=ScriptedLlmPort(["好的"]),
    )
    sink = InMemoryTraceSink()

    async for _ in Orchestrator(ports=ports, sink=sink).run(
        ChatRequest(message="我头疼发烧三天了"), session_id=7
    ):
        pass

    spans = {span.name: span for span in sink.spans}
    decision = sink.routes[0]
    # 路由决策可还原
    assert decision.skills_run == [
        "safety-gate",
        "symptom-normalization",
        "vector-retrieval",
        "graph-inference",
        "orchestration",
    ]
    # 安全门判定可还原
    assert spans["safety-gate"].detail["decision"] == "allow"
    # 引用逐条可还原（序号 / 文件名 / 距离）
    assert spans["vector-retrieval"].detail["references"] == [
        {"index": 1, "file_name": "指南.md", "distance": 0.3}
    ]
    # 候选疾病可还原
    assert spans["graph-inference"].detail["candidates"][0]["disease"] == "感冒"
    # 生成只留长度类事实，不含答案原文
    assert spans["llm"].detail["answer_length"] == len("好的")
    assert set(spans["llm"].detail) == {"prompt_chars", "chunk_count", "answer_length"}


async def test_detail_holds_more_than_the_digest_limit_without_raw_text():
    sink = InMemoryTraceSink()
    message = SIX_RED_FLAGS + "。" + "补充描述" * 20

    await SafetyGateSkill().invoke({"message": message}, _context(sink))

    span = sink.spans[0]
    assert span.detail is not None
    # detail 不受 200 字摘要上限约束……
    assert len(json.dumps(span.detail, ensure_ascii=False)) > DIGEST_LIMIT
    # ……但仍不得落整段患者原文（只保留命中的原文片段）。
    serialized = json.dumps(span.detail, ensure_ascii=False)
    assert "补充描述" not in serialized


@pytest.fixture
def migrated_url(tmp_path) -> str:
    db_path = tmp_path / "detail.db"
    config = Config(str(SERVER_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    command.upgrade(config, "head")
    return f"sqlite+aiosqlite:///{db_path}"


@pytest.fixture
async def session_factory(migrated_url):
    engine = create_async_engine(migrated_url)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def test_detail_is_persisted_and_read_back(session_factory):
    trace = new_trace_id()
    detail = {
        "rule_version": RULES_VERSION,
        "red_flags": [
            {"id": "severe-bleeding", "matched_surface": "吐血", "severity": "emergency"}
        ],
    }

    async with session_factory() as session:
        await TraceRepository(session).record_span(
            Span(
                trace_id=trace,
                name="safety-gate",
                status="ok",
                duration_ms=2,
                input_digest="in",
                output_digest="out",
                started_at=T0,
                detail=detail,
            )
        )
        await session.commit()

    async with session_factory() as session:
        span = (await TraceRepository(session).spans_for(trace))[0]

    assert span.detail == detail
