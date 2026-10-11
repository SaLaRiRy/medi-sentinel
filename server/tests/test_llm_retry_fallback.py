"""TICKET-AC-08：超时重试（只在首字节之前）与备用模型故障转移。

全部走 `httpx.MockTransport`，不发真实网络请求；退避用假的 `sleep` 记账，
不让测试真的等 1.5 秒。
"""

import httpx
import pytest

from core.config import Settings
from skills.fallback_llm import FallbackLlmAdapter
from skills.llm_http import (
    BACKOFF_BASE_SECONDS,
    MAX_ATTEMPTS,
    HttpLlmAdapter,
)


def sse(*chunks: str) -> bytes:
    body = "".join(
        f'data: {{"choices":[{{"delta":{{"content":"{chunk}"}}}}]}}\n\n'
        for chunk in chunks
    )
    return (body + "data: [DONE]\n\n").encode("utf-8")


def sse_partial(*chunks: str) -> bytes:
    """**不带** `[DONE]` 的 SSE 前缀：流还没结束，读下去才会出错。"""
    return "".join(
        f'data: {{"choices":[{{"delta":{{"content":"{chunk}"}}}}]}}\n\n'
        for chunk in chunks
    ).encode("utf-8")


class Exploding(httpx.AsyncByteStream):
    """先吐若干字节，再抛错 —— 用来构造"已经吐字之后才失败"。"""

    def __init__(self, prefix: bytes, error: Exception) -> None:
        self._prefix = prefix
        self._error = error

    async def __aiter__(self):
        yield self._prefix
        raise self._error


def adapter(handler):
    """把每次调用交给 `handler(attempt, request)` 的适配器。"""
    calls = {"count": 0}

    def dispatch(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return handler(calls["count"], request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(dispatch))
    return HttpLlmAdapter(
        base_url="https://api.test/v1", api_key="k", model="m", client=client
    ), calls


async def collect(llm, prompt="你好"):
    return [chunk async for chunk in llm.stream(prompt)]


@pytest.fixture(autouse=True)
def instant_backoff(monkeypatch):
    """记下退避时长但不真的睡。"""
    delays: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    monkeypatch.setattr("skills.llm_http.asyncio.sleep", fake_sleep)
    return delays


# --- 超时重试 -----------------------------------------------------------------


async def test_a_transient_connect_error_is_retried(instant_backoff):
    def handler(attempt, request):
        if attempt < 3:
            raise httpx.ConnectError("connection refused")
        return httpx.Response(200, content=sse("第一段", "第二段"))

    llm, calls = adapter(handler)
    try:
        assert await collect(llm) == ["第一段", "第二段"]
        assert calls["count"] == 3
        # 退避是指数式的：0.5 → 1.0
        assert instant_backoff == [BACKOFF_BASE_SECONDS, BACKOFF_BASE_SECONDS * 2]
    finally:
        await llm.close()


async def test_retries_stop_at_the_attempt_cap(instant_backoff):
    def handler(attempt, request):
        raise httpx.ConnectError("still down")

    llm, calls = adapter(handler)
    try:
        with pytest.raises(httpx.ConnectError):
            await collect(llm)
        assert calls["count"] == MAX_ATTEMPTS
        assert len(instant_backoff) == MAX_ATTEMPTS - 1
    finally:
        await llm.close()


async def test_a_timeout_before_the_first_chunk_becomes_timeout_error(instant_backoff):
    def handler(attempt, request):
        raise httpx.ReadTimeout("too slow")

    llm, _ = adapter(handler)
    try:
        with pytest.raises(TimeoutError):
            await collect(llm)
    finally:
        await llm.close()


async def test_no_retry_once_a_chunk_has_been_emitted(instant_backoff):
    """已经吐字之后再重试，前端会看到两段拼接的回答 —— 绝不允许。"""
    received: list[str] = []

    def handler(attempt, request):
        return httpx.Response(
            200,
            stream=Exploding(
                sse_partial("第一段"), httpx.ReadTimeout("mid-stream")
            ),
        )

    llm, calls = adapter(handler)
    try:
        with pytest.raises(TimeoutError):
            async for chunk in llm.stream("你好"):
                received.append(chunk)
        assert received == ["第一段"]
        assert calls["count"] == 1
        assert instant_backoff == []
    finally:
        await llm.close()


async def test_an_http_status_error_is_not_retried(instant_backoff):
    def handler(attempt, request):
        return httpx.Response(500, json={"error": "boom"})

    llm, calls = adapter(handler)
    try:
        with pytest.raises(httpx.HTTPStatusError):
            await collect(llm)
        assert calls["count"] == 1
    finally:
        await llm.close()


# --- 备用模型故障转移 ---------------------------------------------------------


class Scripted:
    def __init__(self, chunks=(), *, error: Exception | None = None, after: int = 0):
        self._chunks = list(chunks)
        self._error = error
        self._after = after
        self.calls = 0

    async def stream(self, prompt: str):
        self.calls += 1
        for index, chunk in enumerate(self._chunks):
            if self._error is not None and index == self._after:
                raise self._error
            yield chunk
        if self._error is not None and self._after >= len(self._chunks):
            raise self._error


async def test_a_failing_primary_hands_over_to_the_secondary():
    primary = Scripted(error=httpx.ConnectError("down"))
    secondary = Scripted(["备用回答"])

    chunks = await collect(FallbackLlmAdapter(primary, secondary))

    assert chunks == ["备用回答"]
    assert primary.calls == 1 and secondary.calls == 1


async def test_a_primary_that_emitted_before_failing_is_not_replaced():
    primary = Scripted(["半句"], error=RuntimeError("断了"), after=1)
    secondary = Scripted(["备用回答"])
    received: list[str] = []

    with pytest.raises(RuntimeError):
        async for chunk in FallbackLlmAdapter(primary, secondary).stream("你好"):
            received.append(chunk)

    assert received == ["半句"]
    assert secondary.calls == 0


async def test_a_healthy_primary_never_calls_the_secondary():
    primary = Scripted(["主回答"])
    secondary = Scripted(["备用回答"])

    assert await collect(FallbackLlmAdapter(primary, secondary)) == ["主回答"]
    assert secondary.calls == 0


async def test_both_failing_still_raises_so_the_contract_holds():
    primary = Scripted(error=TimeoutError("slow"))
    secondary = Scripted(error=TimeoutError("slow too"))

    with pytest.raises(TimeoutError):
        await collect(FallbackLlmAdapter(primary, secondary))


# --- 装配与死配置 -------------------------------------------------------------


def test_build_llm_wraps_a_fallback_only_when_configured():
    from adapters import build_llm

    base = {
        "openai_api_key": "k",
        "openai_base_url": "https://api.test/v1",
        "llm_model": "main",
        # 本测试测的是「要不要包故障转移」，与用哪个后端无关，固定成 http。
        "llm_backend": "http",
    }
    plain = build_llm(Settings(_env_file=None, **base))
    wrapped = build_llm(Settings(_env_file=None, fallback_llm_model="backup", **base))

    assert isinstance(plain, HttpLlmAdapter)
    assert isinstance(wrapped, FallbackLlmAdapter)


def test_the_dead_chunking_knobs_are_gone_from_settings():
    """三个「配置了却从不生效」的字段已删除；真正的常量在各自的模块里。"""
    settings = Settings(_env_file=None)

    assert not hasattr(settings, "chunk_size")
    assert not hasattr(settings, "chunk_overlap")
    assert not hasattr(settings, "retrieval_top_k")
    assert settings.fallback_llm_model == ""
