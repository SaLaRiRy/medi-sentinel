"""TICKET-025: the real streaming LLM adapter (`skills.llm_http`).

`httpx` is mocked (`httpx.MockTransport`), so no test ever opens a socket: the
adapter's outbound request shape, its parsing of the upstream SSE stream, and
the way a deadline or an unreachable upstream reaches the B-1 error contract
(SPEC.md 4.1 B-3, 5.2, 5.5) are all asserted without touching a provider.
"""

import json
import re
from pathlib import Path

import httpx
import pytest

from adapters import build_llm
from core.config import Settings
from skills.orchestration import ChatRequest, OrchestrationPorts, Orchestrator
from skills.llm_http import HttpLlmAdapter
from skills.ports import UnavailableLlmPort
from skills.trace import InMemoryTraceSink
from tests.doubles import CountingGraphPort, CountingRetrievalPort

BASE_URL = "https://llm.example.com/compatible-mode/v1"
SERVER_ROOT = Path(__file__).resolve().parents[1]


def _sse_line(content: str) -> str:
    payload = json.dumps(
        {"choices": [{"delta": {"content": content}}]}, ensure_ascii=False
    )
    return f"data: {payload}\n\n"


def _sse_body(chunks: list[str]) -> bytes:
    body = "".join(_sse_line(chunk) for chunk in chunks) + "data: [DONE]\n\n"
    return body.encode("utf-8")


def build_adapter(handler) -> HttpLlmAdapter:
    return HttpLlmAdapter(
        base_url=BASE_URL,
        api_key="test-key",
        model="qwen3.8-flash",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


async def test_stream_posts_a_streaming_chat_completion_and_yields_each_delta():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, content=_sse_body(["您好，", "建议多休息。"]))

    adapter = build_adapter(handler)

    chunks = [chunk async for chunk in adapter.stream("我头疼")]

    assert chunks == ["您好，", "建议多休息。"]
    assert seen["url"] == f"{BASE_URL}/chat/completions"
    assert seen["auth"] == "Bearer test-key"
    assert seen["body"]["model"] == "qwen3.8-flash"
    assert seen["body"]["stream"] is True
    assert seen["body"]["messages"] == [{"role": "user", "content": "我头疼"}]


async def test_a_deadline_is_surfaced_as_timeout_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("deadline exceeded", request=request)

    adapter = build_adapter(handler)

    with pytest.raises(TimeoutError):
        [chunk async for chunk in adapter.stream("我头疼")]


async def test_an_unreachable_upstream_is_not_a_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    adapter = build_adapter(handler)

    with pytest.raises(httpx.ConnectError):
        [chunk async for chunk in adapter.stream("我头疼")]


async def _collect(adapter: HttpLlmAdapter, message: str = "你好，我想咨询健康问题"):
    ports = OrchestrationPorts(
        graph=CountingGraphPort(), retrieval=CountingRetrievalPort(), llm=adapter
    )
    orchestrator = Orchestrator(ports=ports, sink=InMemoryTraceSink())
    return [
        frame
        async for frame in orchestrator.run(
            ChatRequest(message=message), session_id=1
        )
    ]


async def test_adapter_deltas_map_to_content_frames_without_reordering_the_stream():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=_sse_body(["您好，", "建议多休息。"]))

    frames = await _collect(build_adapter(handler))

    assert [frame["type"] for frame in frames] == [
        "session",
        "trace",
        "route",
        "content",
        "content",
        "done",
    ]
    assert [frame["content"] for frame in frames if frame["type"] == "content"] == [
        "您好，",
        "建议多休息。",
    ]


async def test_a_timed_out_adapter_ends_the_stream_with_a_504_error_frame():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("deadline exceeded", request=request)

    frames = await _collect(build_adapter(handler))

    assert frames[-1]["type"] == "error"
    assert frames[-1]["code"] == 504
    assert "done" not in [frame["type"] for frame in frames]


async def test_an_unreachable_adapter_ends_the_stream_with_a_503_error_frame():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    frames = await _collect(build_adapter(handler))

    assert frames[-1]["type"] == "error"
    assert frames[-1]["code"] == 503
    assert "done" not in [frame["type"] for frame in frames]


def test_build_llm_returns_the_real_adapter_when_key_and_base_url_are_set():
    llm = build_llm(
        Settings(
            openai_api_key="test-key",
            openai_base_url="https://llm.example.com/v1",
        )
    )

    assert isinstance(llm, HttpLlmAdapter)


@pytest.mark.parametrize(
    ("api_key", "base_url"),
    [("", "https://llm.example.com/v1"), ("test-key", ""), ("", "")],
)
def test_build_llm_falls_back_to_unavailable_when_configuration_is_incomplete(
    api_key, base_url
):
    llm = build_llm(Settings(openai_api_key=api_key, openai_base_url=base_url))

    assert isinstance(llm, UnavailableLlmPort)


async def test_create_app_wires_the_configured_llm_adapter_and_closes_it_on_shutdown():
    from main import create_app

    app = create_app(
        Settings(
            database_url="sqlite+aiosqlite:///:memory:",
            openai_api_key="test-key",
            openai_base_url="https://llm.example.com/v1",
        )
    )
    async with app.router.lifespan_context(app):
        llm = app.state.orchestration_ports.llm
        assert isinstance(llm, HttpLlmAdapter)
        _ = llm.client  # force the lazy client into existence
        assert not llm.client.is_closed

    assert llm.client.is_closed


async def test_create_app_falls_back_to_the_unavailable_port_without_llm_config():
    from main import create_app

    app = create_app(
        Settings(
            database_url="sqlite+aiosqlite:///:memory:",
            openai_api_key="",
            openai_base_url="",
        )
    )
    async with app.router.lifespan_context(app):
        assert isinstance(app.state.orchestration_ports.llm, UnavailableLlmPort)


def test_llm_config_literal_defaults_match_the_ticket():
    fields = Settings.model_fields

    assert fields["openai_api_key"].default == ""
    assert (
        fields["openai_base_url"].default
        == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    assert fields["llm_model"].default == "qwen3.8-flash"
    assert fields["embedding_model"].default == "text-embedding-v4"


@pytest.mark.parametrize(
    "name", ["OPENAI_API_KEY", "OPENAI_BASE_URL", "LLM_MODEL", "EMBEDDING_MODEL"]
)
def test_env_example_lists_the_llm_variables_with_blank_values(name):
    text = (SERVER_ROOT / ".env.example").read_text(encoding="utf-8")

    message = f"{name} is not documented in .env.example"
    assert re.search(rf"^{name}=$", text, re.M), message
