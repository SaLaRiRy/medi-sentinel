"""B-1: the safety short-circuit — a red-flag input never reaches the model.

The safety gate is a process rule, so a hit ends the consult deterministically:
no normalization, no retrieval, no graph, no model call — just the `safety`
frame and a terminal `done` (SPEC.md 3.5, 5.5 不变量 2, 6.3 AC-E-02).
"""

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from skills.orchestration import ChatRequest, OrchestrationPorts, Orchestrator
from skills.trace import InMemoryTraceSink
from tests.doubles import (
    CountingGraphPort,
    CountingRetrievalPort,
    HitsGraphPort,
    HitsRetrievalPort,
    ScriptedLlmPort,
    ThrowingLlmPort,
)

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"

RED_FLAG_MESSAGE = "胸口剧痛，出冷汗，喘不上气"
PLAIN_MESSAGE = "我头疼发烧三天了"
SKIPPED_ON_INTERCEPT = {
    "symptom-normalization",
    "vector-retrieval",
    "graph-inference",
    "orchestration",
}


def build(graph=None, retrieval=None, llm=None):
    graph = graph or CountingGraphPort()
    retrieval = retrieval or CountingRetrievalPort()
    llm = llm or ScriptedLlmPort(["您好"])
    sink = InMemoryTraceSink()
    orchestrator = Orchestrator(
        OrchestrationPorts(graph=graph, retrieval=retrieval, llm=llm), sink
    )
    return orchestrator, sink, graph, retrieval, llm


async def collect(orchestrator, message, **kwargs):
    return [
        frame
        async for frame in orchestrator.run(ChatRequest(message=message), **kwargs)
    ]


def frame_of(frames, frame_type):
    return next(frame for frame in frames if frame["type"] == frame_type)


def trace_id_of(frames):
    return frame_of(frames, "trace")["trace_id"]


async def test_red_flag_input_short_circuits_the_whole_chain():
    orchestrator, _, _, _, _ = build()

    frames = await collect(orchestrator, RED_FLAG_MESSAGE, session_id=7)

    assert [frame["type"] for frame in frames] == [
        "session",
        "trace",
        "route",
        "safety",
        "done",
    ]
    assert frames[0] == {"type": "session", "session_id": 7}
    done = frame_of(frames, "done")
    assert done["references"] == []
    assert done["graph"] == []
    assert done["degraded"] == []
    assert done["coverage_note"] is None
    assert done["trace_id"] == trace_id_of(frames)  # SPEC.md 5.5 不变量 5


async def test_red_flag_input_never_calls_the_model_or_either_branch():
    orchestrator, _, graph, retrieval, llm = build()

    await collect(orchestrator, RED_FLAG_MESSAGE, session_id=1)

    assert llm.prompts == []
    assert graph.calls == []
    assert retrieval.calls == []


async def test_red_flag_input_does_not_touch_a_working_model_port():
    # A throwing model port makes a stray call loud instead of silent (SPEC.md 4.1 B-3).
    orchestrator, _, _, _, _ = build(llm=ThrowingLlmPort())

    frames = await collect(orchestrator, RED_FLAG_MESSAGE, session_id=1)

    assert "error" not in [frame["type"] for frame in frames]
    assert frame_of(frames, "done")


async def test_red_flag_trace_holds_only_the_safety_gate_span():
    orchestrator, sink, _, _, _ = build()

    frames = await collect(orchestrator, RED_FLAG_MESSAGE, session_id=1)
    spans = await sink.spans_for(trace_id_of(frames))

    assert [span.name for span in spans] == ["safety-gate"]
    assert spans[0].status == "ok"


async def test_red_flag_route_runs_only_the_safety_gate():
    orchestrator, sink, _, _, _ = build()

    frames = await collect(orchestrator, RED_FLAG_MESSAGE, session_id=1)
    route = frame_of(frames, "route")

    assert route["skills_run"] == ["safety-gate"]
    assert {
        skipped["skill"] for skipped in route["skills_skipped"]
    } == SKIPPED_ON_INTERCEPT
    assert all(skipped["reason"] for skipped in route["skills_skipped"])
    decision = await sink.route_for(trace_id_of(frames))
    assert decision is not None
    assert decision.skills_run == ["safety-gate"]


async def test_safety_frame_matches_the_frozen_sse_contract():
    orchestrator, _, _, _, _ = build()

    frames = await collect(orchestrator, RED_FLAG_MESSAGE, session_id=1)
    safety = frame_of(frames, "safety")

    Draft202012Validator(
        json.loads((CONTRACTS / "sse-events.json").read_text(encoding="utf-8"))
    ).validate(safety)
    # The wire vocabulary is the frozen contract's, spelled exactly as there.
    assert safety["decision"] == "intercept"
    assert safety["level"] in {"emergency", "urgent"}
    assert {flag["id"] for flag in safety["red_flags"]} == {"chest-pain", "dyspnea"}
    for flag in safety["red_flags"]:
        assert set(flag) == {"id", "label", "matched_surface", "severity"}


async def test_a_plain_input_still_takes_the_normal_path():
    orchestrator, _, _, _, llm = build(
        graph=HitsGraphPort(
            [{"disease": "感冒", "matched_symptoms": ["发热"], "department": None}]
        ),
        retrieval=HitsRetrievalPort(
            [
                {
                    "content": "发热期间应多饮水。",
                    "metadata": {"file_name": "感冒指南.md"},
                    "distance": 0.2,
                }
            ]
        ),
    )

    frames = await collect(orchestrator, PLAIN_MESSAGE, session_id=1)

    types = [frame["type"] for frame in frames]
    assert "safety" not in types
    assert types.count("content") == 1
    assert llm.prompts
