"""The doubles SPEC.md 4.1 names: counting fakes, and a throwing LLM port."""

from collections.abc import AsyncIterator, Sequence
from typing import Any, Mapping


class CountingGraphPort:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    async def infer_diseases(self, symptoms: Sequence[str]) -> Sequence[Mapping[str, Any]]:
        self.calls.append(("infer_diseases", tuple(symptoms)))
        return []

    async def neighbors(self, entity: str, depth: int = 1) -> Mapping[str, Any]:
        self.calls.append(("neighbors", entity, depth))
        return {}


class CountingRetrievalPort:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def search(self, query: str, top_k: int = 5) -> Sequence[Mapping[str, Any]]:
        self.calls.append((query, top_k))
        return []


class HitsGraphPort:
    """Returns canned disease records and records the symptom set it was asked
    about (SPEC.md 4.1 B-3)."""

    def __init__(self, records: Sequence[Mapping[str, Any]] = ()) -> None:
        self.records = list(records)
        self.calls: list[tuple[str, ...]] = []

    async def infer_diseases(self, symptoms: Sequence[str]) -> Sequence[Mapping[str, Any]]:
        self.calls.append(tuple(symptoms))
        return self.records

    async def neighbors(self, entity: str, depth: int = 1) -> Mapping[str, Any]:
        return {}


class ThrowingGraphPort:
    """Any query fails, as an unavailable graph store does (SPEC.md 3.6)."""

    async def infer_diseases(self, symptoms: Sequence[str]) -> Sequence[Mapping[str, Any]]:
        raise RuntimeError("graph unavailable")

    async def neighbors(self, entity: str, depth: int = 1) -> Mapping[str, Any]:
        raise RuntimeError("graph unavailable")


class HitsRetrievalPort:
    """Returns canned hits and records every query (SPEC.md 4.1 B-3)."""

    def __init__(self, hits: Sequence[Mapping[str, Any]] = ()) -> None:
        self.hits = list(hits)
        self.calls: list[tuple[str, int]] = []

    async def search(self, query: str, top_k: int = 5) -> Sequence[Mapping[str, Any]]:
        self.calls.append((query, top_k))
        return self.hits


class ThrowingRetrievalPort:
    """Any call fails, as an unavailable vector index does (SPEC.md 3.6)."""

    async def search(self, query: str, top_k: int = 5) -> Sequence[Mapping[str, Any]]:
        raise RuntimeError("vector index unavailable")


class ThrowingLlmPort:
    """Any call to this port is a test failure (SPEC.md 4.1 B-3)."""

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        raise AssertionError("the LLM must not be called on this path")
        yield ""  # pragma: no cover - unreachable, keeps this an async generator


class FailingLlmPort:
    """The upstream model is down: every call fails (SPEC.md 5.2 `503 上游不可用`)."""

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        raise RuntimeError("model unavailable")
        yield ""  # pragma: no cover - unreachable, keeps this an async generator


class TimedOutLlmPort:
    """The upstream model misses its deadline (SPEC.md 5.2 `504 上游超时`).

    The timeout itself belongs to the adapter (SPEC.md 4.1 B-3 "不测超时实现");
    the port surfaces it as `TimeoutError`, which is what `asyncio.timeout` and
    `asyncio.wait_for` raise on Python 3.11+.
    """

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        raise TimeoutError("model deadline exceeded")
        yield ""  # pragma: no cover - unreachable, keeps this an async generator


class InterruptedLlmPort:
    """Streams a first chunk, then the upstream dies mid-answer: partial content
    stays on the wire and the stream still ends with `error` (SPEC.md 5.5 不变量 4)."""

    def __init__(
        self, chunks: Sequence[str] = ("您好，",), error: Exception | None = None
    ) -> None:
        self._chunks = list(chunks)
        self._error = error or TimeoutError("model deadline exceeded")

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        for chunk in self._chunks:
            yield chunk
        raise self._error


class StubLlmPort:
    async def stream(self, prompt: str) -> AsyncIterator[str]:
        yield ""


class ScriptedLlmPort:
    """Streams canned chunks and records every prompt it was handed, so prompt
    assembly and "the LLM was called exactly once" are both assertable
    (SPEC.md 4.1 B-3)."""

    def __init__(self, chunks: Sequence[str] = ("好的", "请及时就医")) -> None:
        self.chunks = list(chunks)
        self.prompts: list[str] = []

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        self.prompts.append(prompt)
        for chunk in self.chunks:
            yield chunk


class BarrierGraphPort:
    """Arrives at a shared barrier before answering, so a test can prove the
    graph branch and the retrieval branch run concurrently (SPEC.md 2.3 / 6.1)."""

    def __init__(self, barrier: "object") -> None:
        self._barrier = barrier
        self.calls: list[tuple[str, ...]] = []

    async def infer_diseases(self, symptoms: Sequence[str]) -> Sequence[Mapping[str, Any]]:
        self.calls.append(tuple(symptoms))
        await self._barrier.wait()
        return []

    async def neighbors(self, entity: str, depth: int = 1) -> Mapping[str, Any]:
        return {}


class BarrierRetrievalPort:
    """The retrieval half of the same barrier."""

    def __init__(self, barrier: "object") -> None:
        self._barrier = barrier
        self.calls: list[tuple[str, int]] = []

    async def search(self, query: str, top_k: int = 5) -> Sequence[Mapping[str, Any]]:
        self.calls.append((query, top_k))
        await self._barrier.wait()
        return []
