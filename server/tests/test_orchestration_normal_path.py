"""B-1: the milestone — one consult's whole chain on the normal path.

Safety gate → normalization → two parallel branches → context assembly → the
single LLM call → SSE frames, with the trace that a replay can be driven from.
All external dependencies are replaced at B-3, never at B-1 (SPEC.md 4.1).
"""

import asyncio
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from skills.orchestration import (
    ChatRequest,
    ChatTurn,
    OrchestrationPorts,
    Orchestrator,
)
from skills.orchestration.prompt import (
    CONTEXT_FALLBACK,
    HISTORY_LIMIT,
    PROMPT_GRAPH_LIMIT,
    SAFETY_CONSTRAINTS,
)
from skills.graph_inference import to_candidates
from skills.trace import InMemoryTraceSink
from tests.doubles import (
    BarrierGraphPort,
    BarrierRetrievalPort,
    HitsGraphPort,
    HitsRetrievalPort,
    ScriptedLlmPort,
)

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"

MESSAGE = "我头疼发烧三天了"
HITS = [
    {
        "content": "高血压患者应定期监测血压，低盐饮食并规律服药。",
        "metadata": {"file_name": "高血压防治指南.md"},
        "distance": 0.12,
    },
    {
        "content": "发热期间应多饮水、注意休息。",
        "metadata": {"file_name": "感冒与流感指南.md"},
        "distance": 0.31,
    },
]
DISEASES = [
    {"disease": "感冒", "matched_symptoms": ["发热", "头痛"], "department": "呼吸内科"},
    {"disease": "偏头痛", "matched_symptoms": ["头痛"], "department": None},
]


def build(
    graph=None, retrieval=None, llm=None, sink=None
) -> tuple[Orchestrator, InMemoryTraceSink, HitsGraphPort, HitsRetrievalPort, ScriptedLlmPort]:
    graph = graph or HitsGraphPort(DISEASES)
    retrieval = retrieval or HitsRetrievalPort(HITS)
    llm = llm or ScriptedLlmPort(["您好，", "建议多休息并监测体温。"])
    sink = sink or InMemoryTraceSink()
    orchestrator = Orchestrator(
        OrchestrationPorts(graph=graph, retrieval=retrieval, llm=llm), sink
    )
    return orchestrator, sink, graph, retrieval, llm


async def collect(orchestrator: Orchestrator, request: ChatRequest, **kwargs) -> list[dict]:
    return [frame async for frame in orchestrator.run(request, **kwargs)]


def trace_id_of(frames: list[dict]) -> str:
    return next(frame["trace_id"] for frame in frames if frame["type"] == "trace")


def frame_of(frames: list[dict], frame_type: str) -> dict:
    return next(frame for frame in frames if frame["type"] == frame_type)


async def test_normal_path_emits_session_trace_route_content_then_done():
    orchestrator, _, _, _, _ = build()

    frames = await collect(orchestrator, ChatRequest(message=MESSAGE), session_id=7)

    assert [frame["type"] for frame in frames] == [
        "session",
        "trace",
        "route",
        "content",
        "content",
        "done",
    ]
    assert frames[0] == {"type": "session", "session_id": 7}
    assert [frame["type"] for frame in frames].count("done") == 1
    assert "safety" not in [frame["type"] for frame in frames]


async def test_route_runs_all_five_skills_in_the_spec_order():
    orchestrator, sink, _, _, _ = build()

    frames = await collect(orchestrator, ChatRequest(message=MESSAGE), session_id=1)

    route = frame_of(frames, "route")
    assert route["skills_run"] == [
        "safety-gate",
        "symptom-normalization",
        "vector-retrieval",
        "graph-inference",
        "orchestration",
    ]
    assert route["skills_skipped"] == []
    decision = await sink.route_for(trace_id_of(frames))
    assert decision is not None
    assert decision.skills_run == route["skills_run"]


async def test_same_input_and_configuration_route_identically():
    routes = []
    for _ in range(3):
        orchestrator, _, _, _, _ = build()
        frames = await collect(orchestrator, ChatRequest(message=MESSAGE), session_id=1)
        routes.append(frame_of(frames, "route"))

    assert routes[0] == routes[1] == routes[2]


async def test_retrieval_and_graph_receive_independent_inputs():
    orchestrator, _, graph, retrieval, _ = build()

    await collect(orchestrator, ChatRequest(message=MESSAGE), session_id=1)

    # The retrieval branch asks the raw question; the graph branch gets the
    # standardized symptom set. Neither filters the other (SPEC.md 2.3 / 5.2).
    assert retrieval.calls == [(MESSAGE, 5)]
    assert graph.calls == [("头痛", "发热")]


async def test_branches_run_in_parallel_not_back_to_back():
    barrier = asyncio.Barrier(2)
    graph = BarrierGraphPort(barrier)
    retrieval = BarrierRetrievalPort(barrier)
    orchestrator = Orchestrator(
        OrchestrationPorts(
            graph=graph, retrieval=retrieval, llm=ScriptedLlmPort(["答"])
        ),
        InMemoryTraceSink(),
    )

    frames = await asyncio.wait_for(
        collect(orchestrator, ChatRequest(message=MESSAGE), session_id=1), timeout=5
    )

    # Both ports had to be in flight at once to pass the shared barrier; a
    # sequential implementation would deadlock and time out.
    assert graph.calls == [("头痛", "发热")]
    assert retrieval.calls == [(MESSAGE, 5)]
    assert frame_of(frames, "done")["type"] == "done"


async def test_done_carries_references_without_the_internal_distance_field():
    orchestrator, _, _, _, _ = build()

    frames = await collect(orchestrator, ChatRequest(message=MESSAGE), session_id=1)
    done = frame_of(frames, "done")

    assert [reference["index"] for reference in done["references"]] == [1, 2]
    for reference in done["references"]:
        assert set(reference) == {"index", "file_name", "snippet"}
    assert done["references"][0]["file_name"] == "高血压防治指南.md"


async def test_done_carries_the_ranked_candidates_and_a_coverage_note():
    orchestrator, _, _, _, _ = build()

    frames = await collect(orchestrator, ChatRequest(message=MESSAGE), session_id=1)
    done = frame_of(frames, "done")

    assert [candidate["disease"] for candidate in done["graph"]] == ["感冒", "偏头痛"]
    assert done["graph"][0]["coverage"] == 1.0
    assert done["graph"][1]["department"] is None
    assert done["coverage_note"] is None
    assert done["degraded"] == []
    assert done["cost_time"] >= 0


async def test_trace_has_five_skill_spans_and_one_llm_span():
    orchestrator, sink, _, _, _ = build()

    frames = await collect(orchestrator, ChatRequest(message=MESSAGE), session_id=1)
    spans = await sink.spans_for(trace_id_of(frames))

    assert sorted(span.name for span in spans) == [
        "graph-inference",
        "llm",
        "orchestration",
        "safety-gate",
        "symptom-normalization",
        "vector-retrieval",
    ]
    assert all(span.trace_id == trace_id_of(frames) for span in spans)
    assert all(span.status == "ok" for span in spans)
    assert len(spans) == 6


@pytest.mark.parametrize(
    "frame_type", ["session", "trace", "route", "content", "done"]
)
async def test_every_frame_satisfies_the_sse_contract(frame_type):
    orchestrator, _, _, _, _ = build()
    validator = Draft202012Validator(
        json.loads((CONTRACTS / "sse-events.json").read_text(encoding="utf-8"))
    )

    frames = await collect(orchestrator, ChatRequest(message=MESSAGE), session_id=1)
    produced = [frame for frame in frames if frame["type"] == frame_type]

    assert produced, f"the normal path emits no {frame_type} frame"
    for frame in produced:
        validator.validate(frame)


async def test_graph_is_skipped_when_the_combined_symptom_set_is_empty():
    graph = HitsGraphPort(DISEASES)
    orchestrator, sink, _, _, _ = build(graph=graph)

    frames = await collect(orchestrator, ChatRequest(message="你好"), session_id=1)
    route = frame_of(frames, "route")
    trace_id = trace_id_of(frames)
    spans = await sink.spans_for(trace_id)

    assert route["skills_run"] == [
        "safety-gate",
        "symptom-normalization",
        "vector-retrieval",
        "orchestration",
    ]
    assert route["skills_skipped"] == [
        {"skill": "graph-inference", "reason": route["skills_skipped"][0]["reason"]}
    ]
    assert route["skills_skipped"][0]["reason"]
    assert graph.calls == []
    assert "graph-inference" not in [span.name for span in spans]
    assert frame_of(frames, "done")["graph"] == []


async def test_explicit_symptoms_feed_the_graph_branch_but_never_the_safety_gate():
    orchestrator, sink, graph, retrieval, _ = build()

    frames = await collect(
        orchestrator,
        ChatRequest(message="我头疼", explicit_symptoms=["拉肚子"]),
        session_id=1,
    )
    trace_id = trace_id_of(frames)
    safety_span = next(
        span for span in await sink.spans_for(trace_id) if span.name == "safety-gate"
    )

    # Consumed as structured hint: aliases normalize through the single vocabulary.
    assert graph.calls == [("头痛", "腹泻")]
    assert retrieval.calls == [("我头疼", 5)]
    # The safety decision is made on the patient's own words only, so a
    # structured field can never disarm the process rule (SPEC.md 3.5).
    assert "我头疼" in safety_span.input_digest
    assert "拉肚子" not in safety_span.input_digest


async def test_explicit_symptoms_alone_are_enough_to_reach_the_graph():
    orchestrator, _, graph, _, _ = build()

    frames = await collect(
        orchestrator,
        ChatRequest(message="你好", explicit_symptoms=["头疼"]),
        session_id=1,
    )

    assert graph.calls == [("头痛",)]
    assert "graph-inference" in frame_of(frames, "route")["skills_run"]


async def test_prompt_follows_the_documented_assembly_rules():
    llm = ScriptedLlmPort(["答"])
    orchestrator, _, _, _, _ = build(llm=llm)
    history = [ChatTurn(role="user", content=f"问题{index}") for index in range(8)]

    await collect(
        orchestrator,
        ChatRequest(message=MESSAGE),
        session_id=1,
        history=history,
    )

    prompt = llm.prompts[0]
    # System prompt carries exactly the four medical-safety constraints.
    assert prompt.count("你是AI智能医疗问诊助手") == 1
    for constraint in SAFETY_CONSTRAINTS:
        assert constraint in prompt
    assert HISTORY_LIMIT == 6
    # History is truncated to the most recent six turns, oldest dropped first.
    assert "问题2" in prompt and "问题7" in prompt
    assert "问题0" not in prompt and "问题1" not in prompt
    # Context is injected inside the current user prompt, before the question.
    assert prompt.index("参考知识：") < prompt.index("用户问题：")
    assert prompt.index("参考知识：") > prompt.index("[当前问题]")
    assert "用户问题：" + MESSAGE in prompt
    assert "[文档1]" in prompt
    assert "知识图谱推理结果：" in prompt


async def test_graph_context_is_capped_at_five_while_done_returns_all_candidates():
    records = [
        {"disease": "感冒", "matched_symptoms": ["发热", "头痛"], "department": "呼吸内科"},
        {"disease": "偏头痛", "matched_symptoms": ["头痛"], "department": None},
        {"disease": "鼻窦炎", "matched_symptoms": ["头痛"], "department": "耳鼻喉科"},
        {"disease": "脑膜炎", "matched_symptoms": ["发热"], "department": "神经内科"},
        {"disease": "肺炎", "matched_symptoms": ["发热"], "department": "呼吸内科"},
        {"disease": "中耳炎", "matched_symptoms": ["发热"], "department": "耳鼻喉科"},
    ]
    llm = ScriptedLlmPort(["答"])
    orchestrator, _, _, _, _ = build(graph=HitsGraphPort(records), llm=llm)

    frames = await collect(orchestrator, ChatRequest(message=MESSAGE), session_id=1)

    assert PROMPT_GRAPH_LIMIT == 5
    assert len(frame_of(frames, "done")["graph"]) == 6
    prompt = llm.prompts[0]
    ordered = [candidate.disease for candidate in to_candidates(records, ["头痛", "发热"])]
    assert all(disease in prompt for disease in ordered[:PROMPT_GRAPH_LIMIT])
    assert ordered[PROMPT_GRAPH_LIMIT] not in prompt
    assert frame_of(frames, "done")["coverage_note"]


async def test_context_falls_back_when_both_branches_are_empty():
    llm = ScriptedLlmPort(["答"])
    orchestrator, _, _, _, _ = build(
        graph=HitsGraphPort([]), retrieval=HitsRetrievalPort([]), llm=llm
    )

    await collect(orchestrator, ChatRequest(message=MESSAGE), session_id=1)

    assert CONTEXT_FALLBACK == "暂无相关知识库内容。"
    assert "参考知识：\n" + CONTEXT_FALLBACK in llm.prompts[0]


async def test_prompt_context_uses_the_whole_chunk_not_just_the_snippet():
    """FUNCTIONAL_SPEC 5.3: the reference keeps the first 200 characters, but the
    prompt fragment is 「[文档N] <整块正文>」 — the Skill must expose both."""
    content = "高血压患者应低盐饮食、规律服药并定期监测血压。" * 30
    llm = ScriptedLlmPort(["答"])
    orchestrator, _, _, _, _ = build(
        retrieval=HitsRetrievalPort(
            [
                {
                    "content": content,
                    "metadata": {"file_name": "高血压防治指南.md"},
                    "distance": 0.1,
                }
            ]
        ),
        llm=llm,
    )

    frames = await collect(orchestrator, ChatRequest(message=MESSAGE), session_id=1)

    assert f"[文档1] {content}" in llm.prompts[0]
    reference = frame_of(frames, "done")["references"][0]
    assert len(reference["snippet"]) == 200
    assert set(reference) == {"index", "file_name", "snippet"}


async def test_llm_failure_ends_the_stream_with_error_not_done():
    class ExplodingLlm:
        async def stream(self, prompt):
            raise RuntimeError("model unavailable")
            yield ""  # pragma: no cover

    orchestrator, sink, _, _, _ = build(llm=ExplodingLlm())

    frames = await collect(orchestrator, ChatRequest(message=MESSAGE), session_id=1)
    types = [frame["type"] for frame in frames]

    assert types[-1] == "error"
    assert "done" not in types
    assert frame_of(frames, "error")["trace_id"] == trace_id_of(frames)
    llm_span = next(
        span for span in await sink.spans_for(trace_id_of(frames)) if span.name == "llm"
    )
    assert llm_span.status == "error"


async def test_acceptance_scenario_headache_and_fever_runs_end_to_end():
    """AC-E-01: 「我头疼发烧三天了」 — the milestone that must go green."""
    llm = ScriptedLlmPort(["可能的常见原因是上呼吸道感染。"])
    orchestrator, sink, _, _, _ = build(llm=llm)

    frames = await collect(orchestrator, ChatRequest(message=MESSAGE), session_id=1)
    done = frame_of(frames, "done")
    spans = await sink.spans_for(trace_id_of(frames))

    # Normalization produced the standard symptoms that reached the graph.
    graph_span = next(span for span in spans if span.name == "graph-inference")
    assert "头痛" in graph_span.input_digest and "发热" in graph_span.input_digest
    assert llm.prompts[0].count("头痛") >= 1
    # The graph returned candidates and the answer streamed non-empty content.
    assert [candidate["disease"] for candidate in done["graph"]] == ["感冒", "偏头痛"]
    assert [frame["content"] for frame in frames if frame["type"] == "content"] == [
        "可能的常见原因是上呼吸道感染。"
    ]
    assert done["references"] and done["graph"]
    # Five Skill spans plus the single model span.
    assert len([span for span in spans if span.name != "llm"]) == 5
    assert len([span for span in spans if span.name == "llm"]) == 1
