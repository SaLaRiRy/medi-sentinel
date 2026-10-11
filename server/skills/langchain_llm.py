"""LangChain 版本的 `LlmPort`（TICKET-AC-09）。

只替换 B-3 的**实现层**：端口签名、异常契约（超时 → `TimeoutError` → 504，
其他不可用 → 503）与 `HttpLlmAdapter` 完全一致，因此编排、回归回放与 SSE 帧序
一个字都不用改。`HttpLlmAdapter` **保留**，由 `llm_backend=http|langchain` 切换。

为什么现在才做：`SPEC.md` 3.1 的技术栈表一直写着「LangChain **异步调用**」，
而 `llm_http.py` 当初的注释引用错了条款（写的是 3.1，真正支撑手写决定的是 4.1 B-3）。
本票把实现换回规格要求的那一层，并顺手把那条注释改对。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Callable

ChatFactory = Callable[..., Any]

#: 上游超时异常的名字集合：openai / httpx 两家的超时都归一到 TimeoutError。
_TIMEOUT_NAMES = frozenset(
    {"APITimeoutError", "TimeoutException", "ReadTimeout", "ConnectTimeout", "Timeout"}
)


def _is_timeout(error: BaseException) -> bool:
    if isinstance(error, TimeoutError):
        return True
    return any(base.__name__ in _TIMEOUT_NAMES for base in type(error).__mro__)


def _text_of(chunk: Any) -> str:
    """`AIMessageChunk` 的文本增量。

    内容块可能是字符串（`content`）或列表（新版多模态分块），两种都取文本部分；
    与 `HttpLlmAdapter._delta_of` 一样，空增量返回空串、由调用方跳过。
    """
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "".join(parts)
    return ""


def _default_chat_factory(**params: Any) -> Any:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(**params)


class LangChainLlmAdapter:
    """用 `ChatOpenAI.astream()` 实现的流式 `LlmPort`。"""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        chat_factory: ChatFactory | None = None,
    ) -> None:
        self.model = model
        self._params: dict[str, Any] = {
            "model": model,
            "base_url": base_url,
            "api_key": api_key,
            "timeout": timeout,
            "streaming": True,
        }
        self._chat_factory = chat_factory or _default_chat_factory

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        chat = self._chat_factory(**self._params)
        try:
            async for chunk in chat.astream(prompt):
                text = _text_of(chunk)
                if text:
                    yield text
        except Exception as error:
            if _is_timeout(error):
                # The port contract speaks `TimeoutError` (SPEC.md 4.1 B-3).
                raise TimeoutError(str(error)) from error
            raise

    async def close(self) -> None:
        """LangChain 自己管理连接池，这里没有需要显式释放的客户端。"""
