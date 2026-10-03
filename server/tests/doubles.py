"""The doubles SPEC.md 4.1 names: counting fakes, and a throwing LLM port."""

import asyncio
from collections.abc import AsyncIterator, Sequence
from typing import Any, Mapping


class CountingGraphPort:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    async def infer_diseases(self, symptoms: Sequence[str]) -> Sequence[Mapping[str, Any]]:
        self.calls.append(("infer_diseases", tuple(symptoms)))
        return []

    async def full_graph(self) -> Mapping[str, Any]:
        self.calls.append(("full_graph",))
        return {"nodes": [], "edges": []}

    async def neighbors(self, entity: str, depth: int = 1) -> Mapping[str, Any]:
        self.calls.append(("neighbors", entity, depth))
        return {}

    async def search_entities(self, keyword: str) -> Sequence[Mapping[str, Any]]:
        self.calls.append(("search_entities", keyword))
        return []

    async def disease_detail(self, name: str) -> Mapping[str, Any]:
        self.calls.append(("disease_detail", name))
        return {}

    async def node_counts(self) -> Mapping[str, int]:
        self.calls.append(("node_counts",))
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

    async def full_graph(self) -> Mapping[str, Any]:
        return {"nodes": [], "edges": []}

    async def search_entities(self, keyword: str) -> Sequence[Mapping[str, Any]]:
        return []

    async def disease_detail(self, name: str) -> Mapping[str, Any]:
        return {}

    async def node_counts(self) -> Mapping[str, int]:
        return {}


class ThrowingGraphPort:
    """Any query fails, as an unavailable graph store does (SPEC.md 3.6)."""

    async def infer_diseases(self, symptoms: Sequence[str]) -> Sequence[Mapping[str, Any]]:
        raise RuntimeError("graph unavailable")

    async def full_graph(self) -> Mapping[str, Any]:
        raise RuntimeError("graph unavailable")

    async def neighbors(self, entity: str, depth: int = 1) -> Mapping[str, Any]:
        raise RuntimeError("graph unavailable")

    async def search_entities(self, keyword: str) -> Sequence[Mapping[str, Any]]:
        raise RuntimeError("graph unavailable")

    async def disease_detail(self, name: str) -> Mapping[str, Any]:
        raise RuntimeError("graph unavailable")

    async def node_counts(self) -> Mapping[str, int]:
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


class GatedLlmPort:
    """Generation does not produce until the test releases it.

    `started` fires as soon as a generation begins and `calls` counts how many
    began, so a concurrent second request can be proven not to start a second
    generation (SPEC.md 6.1 AC-B-25).
    """

    def __init__(
        self, chunks: Sequence[str] = ("好的",), *, expected_calls: int = 1
    ) -> None:
        self._chunks = list(chunks)
        self._expected_calls = expected_calls
        self._release = asyncio.Event()
        self.started = asyncio.Event()
        self.all_started = asyncio.Event()
        self.calls = 0

    def release(self) -> None:
        self._release.set()

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        self.calls += 1
        self.started.set()
        if self.calls >= self._expected_calls:
            self.all_started.set()
        await self._release.wait()
        for chunk in self._chunks:
            yield chunk


class BlockingLlmPort:
    """Streams one chunk, then holds the model call open until it is cancelled.

    It records *how* the downstream call ended, so a client disconnect can be
    asserted to cancel the model rather than leak it (SPEC.md 6.1 AC-B-26).
    """

    def __init__(self, first_chunk: str = "您好，") -> None:
        self._first_chunk = first_chunk
        self.waiting = asyncio.Event()
        self.cancelled = False
        self.closed = False

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        try:
            yield self._first_chunk
            self.waiting.set()
            await asyncio.Event().wait()
            yield "第二段"  # pragma: no cover - the test cancels before this
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        except GeneratorExit:
            self.closed = True
            raise


class PacedLlmPort:
    """Yields canned chunks with a real suspension between them, so twenty
    concurrent consults actually interleave on the loop (SPEC.md 6.1 AC-B-24)."""

    def __init__(self, chunks: Sequence[str] = ("好的",)) -> None:
        self.chunks = list(chunks)

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        for chunk in self.chunks:
            await asyncio.sleep(0)
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

    async def full_graph(self) -> Mapping[str, Any]:
        return {"nodes": [], "edges": []}

    async def search_entities(self, keyword: str) -> Sequence[Mapping[str, Any]]:
        return []

    async def disease_detail(self, name: str) -> Mapping[str, Any]:
        return {}

    async def node_counts(self) -> Mapping[str, int]:
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


class InMemoryVectorStore:
    """The `VectorStore` port held in memory (TICKET-015)."""

    def __init__(self, *, fail_on_add: bool = False) -> None:
        self.by_file: dict[int, list[str]] = {}
        self.deleted: list[int] = []
        self.fail_on_add = fail_on_add
        self.on_add = None

    async def add_chunks(self, *, file_id: int, file_name: str, chunks) -> int:
        if self.on_add is not None:
            await self.on_add()
        if self.fail_on_add:
            raise RuntimeError("embedding service unavailable")
        self.by_file[file_id] = list(chunks)
        return len(self.by_file[file_id])

    async def delete_by_file_id(self, file_id: int) -> None:
        self.deleted.append(file_id)
        self.by_file.pop(file_id, None)

    async def count_by_file_id(self, file_id: int) -> int:
        return len(self.by_file.get(file_id, []))

    async def search(self, query: str, top_k: int = 5) -> Sequence[Mapping[str, Any]]:
        return []


class ColdScheduler:
    """Records the coroutine instead of running it.

    The test decides when the background vectorization happens, so "the upload
    returned before the file was vectorized" is observable (TICKET-015).
    """

    def __init__(self) -> None:
        self.coroutines: list[Any] = []

    def __call__(self, coroutine: Any) -> Any:
        self.coroutines.append(coroutine)
        return coroutine
