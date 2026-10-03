"""C-1: the contract is an artifact in its own right, checked from both sides.

These tests are the backend half: what the app produces must satisfy the
committed contract, and the contract's change must be visible as a file diff.
"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from core.response import page_result
from skills.orchestration import ChatRequest, OrchestrationPorts, Orchestrator
from skills.trace import InMemoryTraceSink
from tests.doubles import CountingGraphPort, CountingRetrievalPort, StubLlmPort

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"


def _contract(name: str) -> dict:
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def _generated_openapi() -> dict:
    from core.config import Settings
    from main import create_app

    return create_app(Settings()).openapi()


def test_committed_openapi_matches_the_application():
    assert _generated_openapi() == _contract("openapi.json")


def test_contract_declares_health_with_the_response_envelope():
    contract = _contract("openapi.json")

    operation = contract["paths"]["/api/v1/health"]["get"]
    media = operation["responses"]["200"]["content"]["application/json; charset=utf-8"]
    schema_name = media["schema"]["$ref"].rsplit("/", 1)[-1]
    envelope = contract["components"]["schemas"][schema_name]

    assert set(envelope["properties"]) >= {"code", "message", "data"}


def test_sse_schema_covers_every_frame_type_in_the_spec():
    schema = _contract("sse-events.json")

    assert {"session", "trace", "route", "safety", "content", "done", "error"} <= set(
        schema["$defs"]
    )


def test_pagination_payload_has_the_declared_shape():
    envelope = page_result(items=[1, 2], total=2, page=1, page_size=20)

    body = envelope.model_dump()
    assert body["code"] == 200
    assert set(body["data"]) == {"items", "total", "page", "page_size"}
    assert body["data"]["total"] == 2


@pytest.mark.parametrize("frame_type", ["session", "trace", "done"])
async def test_orchestrator_frames_satisfy_the_sse_schema(frame_type):
    """The schema is not decoration: real frames are validated against it."""
    ports = OrchestrationPorts(
        graph=CountingGraphPort(), retrieval=CountingRetrievalPort(), llm=StubLlmPort()
    )
    orchestrator = Orchestrator(ports=ports, sink=InMemoryTraceSink())
    validator = Draft202012Validator(_contract("sse-events.json"))

    frames = [
        frame
        async for frame in orchestrator.run(ChatRequest(message="你好"), session_id=1)
    ]
    produced = [frame for frame in frames if frame["type"] == frame_type]

    assert produced, f"the skeleton emits no {frame_type} frame"
    for frame in produced:
        validator.validate(frame)
