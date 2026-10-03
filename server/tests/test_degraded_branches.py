"""TICKET-009: a degraded branch never breaks the consult.

Vector retrieval and graph inference are enhancement branches. When one is
unavailable the consult still finishes — `done` exactly once, no `error` frame,
HTTP 200 — and `done.degraded` names the unusable branch while the Skill output
and its span keep a non-empty reason. Generation is the one branch that cannot
degrade: it ends the stream with an `error` frame, `503` when the model is
unavailable and `504` when it times out (SPEC.md 3.6, 5.2「降级与失败的区分」, 5.5).

Assertions stay on B-1 and the B-3 doubles (SPEC.md 4.1); no Skill internals are
touched.
"""

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from skills.orchestration import ChatRequest, OrchestrationPorts, Orchestrator
from skills.trace import InMemoryTraceSink
from tests.doubles import (
    FailingLlmPort,
    HitsGraphPort,
    HitsRetrievalPort,
    InterruptedLlmPort,
    ScriptedLlmPort,
    ThrowingGraphPort,
    ThrowingRetrievalPort,
    TimedOutLlmPort,
)

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"

MESSAGE = "我头疼发烧三天了"
HITS = [
    {
        "content": "发热期间应多饮水、注意休息。",
        "metadata": {"file_name": "感冒与流感指南.md"},
        "distance": 0.31,
    },
]
DISEASES = [
    {"disease": "感冒", "matched_symptoms": ["发热", "头痛"], "department": "呼吸内科"},
]


def build(*, graph=None, retrieval=None, llm=None):
    graph = graph if graph is not None else HitsGraphPort(DISEASES)
    retrieval = retrieval if retrieval is not None else HitsRetrievalPort(HITS)
    llm = llm if llm is not None else ScriptedLlmPort(["您好，", "建议多休息。"])
    sink = InMemoryTraceSink()
    orchestrator = Orchestrator(
        OrchestrationPorts(graph=graph, retrieval=retrieval, llm=llm), sink
    )
    return orchestrator, sink, llm


async def collect(orchestrator: Orchestrator, request: ChatRequest) -> list[dict]:
    return [frame async for frame in orchestrator.run(request, session_id=1)]


def trace_id_of(frames: list[dict]) -> str:
    return next(frame["trace_id"] for frame in frames if frame["type"] == "trace")


async def test_unavailable_graph_degrades_and_the_consult_still_completes():
    orchestrator, _, llm = build(graph=ThrowingGraphPort())

    frames = await collect(orchestrator, ChatRequest(message=MESSAGE))
    types = [frame["type"] for frame in frames]
    done = frames[-1]

    assert types[-1] == "done"
    assert types.count("done") == 1
    assert "error" not in types
    assert done["degraded"] == ["graph"]
    assert done["graph"] == []
    # The other branch and the model still ran: degradation does not truncate.
    assert done["references"]
    assert [frame for frame in frames if frame["type"] == "content"]
    assert len(llm.prompts) == 1


async def test_unavailable_retrieval_degrades_and_the_consult_still_completes():
    orchestrator, _, llm = build(retrieval=ThrowingRetrievalPort())

    frames = await collect(orchestrator, ChatRequest(message=MESSAGE))
    types = [frame["type"] for frame in frames]
    done = frames[-1]

    assert types[-1] == "done"
    assert "error" not in types
    assert done["degraded"] == ["retrieval"]
    assert done["references"] == []
    assert done["graph"]
    assert [frame for frame in frames if frame["type"] == "content"]
    assert len(llm.prompts) == 1


async def test_both_branches_can_degrade_in_one_consult():
    orchestrator, _, _ = build(
        graph=ThrowingGraphPort(), retrieval=ThrowingRetrievalPort()
    )

    frames = await collect(orchestrator, ChatRequest(message=MESSAGE))
    done = frames[-1]

    assert done["type"] == "done"
    assert done["degraded"] == ["retrieval", "graph"]
    assert done["references"] == []
    assert done["graph"] == []
    assert "error" not in [frame["type"] for frame in frames]


async def test_a_degraded_done_frame_still_satisfies_the_sse_contract():
    orchestrator, _, _ = build(graph=ThrowingGraphPort())
    validator = Draft202012Validator(
        json.loads((CONTRACTS / "sse-events.json").read_text(encoding="utf-8"))
    )

    frames = await collect(orchestrator, ChatRequest(message=MESSAGE))

    validator.validate(frames[-1])


async def test_degradation_keeps_a_non_empty_reason_in_the_trace():
    orchestrator, sink, _ = build(graph=ThrowingGraphPort())

    frames = await collect(orchestrator, ChatRequest(message=MESSAGE))
    spans = await sink.spans_for(trace_id_of(frames))
    graph_span = next(span for span in spans if span.name == "graph-inference")

    # Degrading is not an error: the branch span stays `ok` and its bounded
    # output summary carries the flag and the reason (SPEC.md 3.7 / 4.1 B-4).
    assert graph_span.status == "ok"
    assert "degraded=True" in graph_span.output_digest
    assert "graph unavailable" in graph_span.output_digest


async def test_a_degraded_branch_leaves_no_skill_span_in_error():
    orchestrator, sink, _ = build(
        graph=ThrowingGraphPort(), retrieval=ThrowingRetrievalPort()
    )

    frames = await collect(orchestrator, ChatRequest(message=MESSAGE))
    spans = await sink.spans_for(trace_id_of(frames))

    assert all(span.status == "ok" for span in spans)
    assert {span.name for span in spans} == {
        "safety-gate",
        "symptom-normalization",
        "vector-retrieval",
        "graph-inference",
        "orchestration",
        "llm",
    }


async def test_unavailable_generation_ends_the_stream_with_a_503_error_frame():
    orchestrator, sink, _ = build(llm=FailingLlmPort())

    frames = await collect(orchestrator, ChatRequest(message=MESSAGE))
    types = [frame["type"] for frame in frames]
    error = frames[-1]

    assert types[-1] == "error"
    assert "done" not in types
    assert error["code"] == 503
    assert error["message"]
    assert error["trace_id"] == trace_id_of(frames)
    llm_span = next(
        span for span in await sink.spans_for(trace_id_of(frames)) if span.name == "llm"
    )
    assert llm_span.status == "error"


async def test_timed_out_generation_ends_the_stream_with_a_504_error_frame():
    orchestrator, sink, _ = build(llm=TimedOutLlmPort())

    frames = await collect(orchestrator, ChatRequest(message=MESSAGE))
    types = [frame["type"] for frame in frames]
    error = frames[-1]

    assert types[-1] == "error"
    assert "done" not in types
    assert error["code"] == 504
    assert error["message"]
    llm_span = next(
        span for span in await sink.spans_for(trace_id_of(frames)) if span.name == "llm"
    )
    assert llm_span.status == "error"


async def test_a_mid_stream_timeout_keeps_the_content_and_ends_with_error():
    orchestrator, _, _ = build(llm=InterruptedLlmPort(["您好，"]))

    frames = await collect(orchestrator, ChatRequest(message=MESSAGE))
    types = [frame["type"] for frame in frames]

    # Content already pushed stays on the wire; the stream still closes with the
    # `error` frame and never emits `done` (SPEC.md 5.5 不变量 4).
    assert [frame["content"] for frame in frames if frame["type"] == "content"] == [
        "您好，"
    ]
    assert types[-1] == "error"
    assert frames[-1]["code"] == 504
    assert "done" not in types
