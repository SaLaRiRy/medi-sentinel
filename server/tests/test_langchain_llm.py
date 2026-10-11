"""TICKET-AC-09：LangChain 版本的 `LlmPort`（`ChatOpenAI.astream()`）。

不联网：`chat_factory` 注入假 chat 对象。真正要证明的是**等价性**——
同样的内容序列，两个适配器产出的增量序列逐字相同；超时照样翻成 `TimeoutError`。
"""

import httpx
import pytest

from core.config import Settings
from skills.langchain_llm import LangChainLlmAdapter, _is_timeout, _text_of
from skills.llm_http import HttpLlmAdapter


class FakeChunk:
    def __init__(self, content):
        self.content = content


class FakeChat:
    """假的 ChatOpenAI：`astream` 依次产出给定内容，或抛出给定异常。"""

    def __init__(self, contents=(), *, error: Exception | None = None, after: int = 0):
        self._contents = list(contents)
        self._error = error
        self._after = after
        self.prompts: list[str] = []

    async def astream(self, prompt: str):
        self.prompts.append(prompt)
        for index, content in enumerate(self._contents):
            if self._error is not None and index == self._after:
                raise self._error
            yield FakeChunk(content)
        if self._error is not None and self._after >= len(self._contents):
            raise self._error


def adapter(chat: FakeChat, **overrides) -> LangChainLlmAdapter:
    params = {
        "base_url": "https://api.test/v1",
        "api_key": "k",
        "model": "m",
        "chat_factory": lambda **kwargs: chat,
    }
    params.update(overrides)
    return LangChainLlmAdapter(**params)


async def collect(llm, prompt="你好"):
    return [chunk async for chunk in llm.stream(prompt)]


# --- 文本抽取 -----------------------------------------------------------------


def test_text_of_handles_strings_blocks_and_empty_content():
    assert _text_of(FakeChunk("你好")) == "你好"
    assert _text_of(FakeChunk([{"type": "text", "text": "你好"}, "世界"])) == "你好世界"
    assert _text_of(FakeChunk(None)) == ""
    assert _text_of(object()) == ""


def test_is_timeout_recognises_both_families():
    class APITimeoutError(Exception):
        pass

    assert _is_timeout(TimeoutError("x"))
    assert _is_timeout(APITimeoutError("x"))
    assert not _is_timeout(RuntimeError("x"))


# --- 流式产出 -----------------------------------------------------------------


async def test_the_adapter_streams_the_chunk_text_in_order():
    chat = FakeChat(["第一", "段", "回答"])

    assert await collect(adapter(chat)) == ["第一", "段", "回答"]
    assert chat.prompts == ["你好"]


async def test_empty_chunks_are_skipped():
    chat = FakeChat(["第一", "", None, "第二"])

    assert await collect(adapter(chat)) == ["第一", "第二"]


async def test_content_blocks_are_flattened():
    chat = FakeChat([[{"type": "text", "text": "块一"}], [{"type": "text", "text": "块二"}]])

    assert await collect(adapter(chat)) == ["块一", "块二"]


async def test_a_timeout_becomes_timeout_error():
    class APITimeoutError(Exception):
        pass

    chat = FakeChat(error=APITimeoutError("too slow"))

    with pytest.raises(TimeoutError):
        await collect(adapter(chat))


async def test_other_failures_are_passed_through_untouched():
    chat = FakeChat(error=RuntimeError("upstream exploded"))

    with pytest.raises(RuntimeError):
        await collect(adapter(chat))


async def test_a_mid_stream_failure_keeps_the_chunks_already_emitted():
    chat = FakeChat(["半句", "另半句"], error=RuntimeError("断了"), after=1)
    received: list[str] = []

    with pytest.raises(RuntimeError):
        async for chunk in adapter(chat).stream("你好"):
            received.append(chunk)

    assert received == ["半句"]


async def test_it_is_a_drop_in_replacement_for_the_http_adapter():
    """同一段内容：两个适配器产出的增量序列逐字相同（端口契约等价）。"""
    contents = ["你好", "，", "这是回答"]
    chat = FakeChat(contents)

    def handler(request: httpx.Request) -> httpx.Response:
        body = "".join(
            f'data: {{"choices":[{{"delta":{{"content":"{chunk}"}}}}]}}\n\n'
            for chunk in contents
        )
        return httpx.Response(200, content=(body + "data: [DONE]\n\n").encode("utf-8"))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    http_adapter = HttpLlmAdapter(
        base_url="https://api.test/v1", api_key="k", model="m", client=client
    )
    try:
        assert await collect(adapter(chat)) == await collect(http_adapter)
    finally:
        await http_adapter.close()


# --- 装配 ---------------------------------------------------------------------


def test_build_llm_defaults_to_langchain_and_can_switch_back_to_http():
    from adapters import build_llm

    base = {
        "openai_api_key": "k",
        "openai_base_url": "https://api.test/v1",
        "llm_model": "main",
    }
    by_default = build_llm(Settings(_env_file=None, **base))
    by_config = build_llm(Settings(_env_file=None, llm_backend="http", **base))

    assert isinstance(by_default, LangChainLlmAdapter)
    assert isinstance(by_config, HttpLlmAdapter)


def test_the_fallback_wraps_whichever_backend_is_chosen():
    from adapters import build_llm
    from skills.fallback_llm import FallbackLlmAdapter

    llm = build_llm(
        Settings(
            _env_file=None,
            openai_api_key="k",
            openai_base_url="https://api.test/v1",
            llm_model="main",
            llm_backend="langchain",
            fallback_llm_model="backup",
        )
    )

    assert isinstance(llm, FallbackLlmAdapter)


def test_the_replay_path_never_imports_langchain():
    """回放必须零外部依赖：`regression/` 的源码里不能出现 langchain。"""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "regression"
    for path in root.glob("*.py"):
        assert "langchain" not in path.read_text(encoding="utf-8").lower(), path.name
