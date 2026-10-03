"""B-1: the top seam — frame order, trace identity, wire-readiness."""

import json

import pytest

from skills.orchestration import ChatRequest, OrchestrationPorts, Orchestrator
from skills.trace import InMemoryTraceSink
from tests.doubles import CountingGraphPort, CountingRetrievalPort, StubLlmPort


@pytest.fixture
def orchestrator() -> Orchestrator:
    ports = OrchestrationPorts(
        graph=CountingGraphPort(), retrieval=CountingRetrievalPort(), llm=StubLlmPort()
    )
    return Orchestrator(ports=ports, sink=InMemoryTraceSink())


async def _frames(orchestrator: Orchestrator) -> list[dict]:
    return [
        frame
        async for frame in orchestrator.run(ChatRequest(message="你好"), session_id=7)
    ]


async def test_session_and_trace_are_the_first_two_frames(orchestrator):
    frames = await _frames(orchestrator)

    assert [frame["type"] for frame in frames[:2]] == ["session", "trace"]
    assert frames[0]["session_id"] == 7


async def test_stream_ends_with_exactly_one_done_frame(orchestrator):
    frames = await _frames(orchestrator)

    assert [frame["type"] for frame in frames].count("done") == 1
    assert frames[-1]["type"] == "done"


async def test_trace_id_is_identical_in_every_frame_that_carries_one(orchestrator):
    frames = await _frames(orchestrator)

    carried = {frame["trace_id"] for frame in frames if "trace_id" in frame}
    assert len(carried) == 1


async def test_frames_are_wire_ready_json(orchestrator):
    frames = await _frames(orchestrator)

    encoded = json.dumps(frames, ensure_ascii=False)

    assert json.loads(encoded) == frames
