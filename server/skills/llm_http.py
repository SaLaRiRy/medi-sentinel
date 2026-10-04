"""真实大模型流式适配器（TICKET-025）。

以 `httpx.AsyncClient` 直连兼容 OpenAI 的 `{base_url}/chat/completions`
（`stream=true`），把上游 SSE 的增量分块逐段产出为 `LlmPort.stream` 的异步
迭代器。全异步、无同步阻塞 I/O，不引入 langchain（SPEC.md 3.1 / 4.1 B-3）。

上游异常按 B-3 的契约外抛：超时统一为 `TimeoutError`（→ `error` 504），其余
不可用异常原样外抛（→ `error` 503）。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

_DATA_PREFIX = "data:"
_DONE = "[DONE]"


class HttpLlmAdapter:
    """直连兼容接口的真实 `LlmPort` 实现。"""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._client = client

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        payload = {
            "model": self._model,
            "stream": True,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            async with self.client.stream(
                "POST", self._url, headers=headers, json=payload
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    delta = _delta_of(line)
                    if delta is None:
                        break
                    if delta:
                        yield delta
        except httpx.TimeoutException as error:
            # The port contract speaks `TimeoutError` (SPEC.md 4.1 B-3); httpx's
            # own timeout family does not inherit from it, so translate here.
            raise TimeoutError(str(error)) from error

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()


def _delta_of(line: str) -> str | None:
    """The incremental text of one upstream SSE line.

    Returns `None` for the terminating `[DONE]` sentinel, `""` for lines that
    carry no text (blank lines, comments, a `finish_reason`-only delta), and the
    delta content otherwise.
    """
    if not line.startswith(_DATA_PREFIX):
        return ""
    data = line[len(_DATA_PREFIX) :].strip()
    if data == _DONE:
        return None
    choices = json.loads(data).get("choices") or []
    if not choices:
        return ""
    return choices[0].get("delta", {}).get("content") or ""
