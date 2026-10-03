"""B-3: the three narrow ports. They exist so tests can count calls — above all,
so "the LLM was not called" is assertable (SPEC.md 4.1, 4.5)."""

from collections.abc import AsyncIterator, Sequence
from typing import Any, Mapping, Protocol, runtime_checkable


@runtime_checkable
class GraphPort(Protocol):
    async def infer_diseases(self, symptoms: Sequence[str]) -> Sequence[Mapping[str, Any]]: ...

    # The read-only view queries behind the graph-view API (TICKET-016, SPEC.md
    # 5.4「知识图谱」). They return the same node/edge payload shape, so the
    # endpoints and the front-end render them with one projection.
    async def full_graph(self) -> Mapping[str, Any]: ...

    async def neighbors(
        self, entity: str, depth: int = 1
    ) -> Mapping[str, Any] | None: ...

    async def search_entities(self, keyword: str) -> Sequence[Mapping[str, Any]]: ...

    async def disease_detail(self, name: str) -> Mapping[str, Any] | None: ...

    async def node_counts(self) -> Mapping[str, int]: ...


@runtime_checkable
class RetrievalPort(Protocol):
    async def search(self, query: str, top_k: int = 5) -> Sequence[Mapping[str, Any]]: ...


@runtime_checkable
class LlmPort(Protocol):
    """The one port generation cannot degrade on (SPEC.md 5.2).

    An adapter that cannot reach the model raises: `TimeoutError` when the
    deadline passes (→ `error` code 504, the timeout itself is infrastructure,
    SPEC.md 4.1 B-3), any other exception when the model is unavailable
    (→ `error` code 503).
    """

    def stream(self, prompt: str) -> AsyncIterator[str]: ...


class UnavailableGraphPort:
    """An explicitly unwired graph branch: it degrades instead of crashing
    (SPEC.md 3.6). The running default is the real `AsyncGraphDatabase` adapter
    (`adapters.build_graph_store`, TICKET-013); this stays for tests and for
    callers that deliberately run without a graph store."""

    def __init__(self, reason: str = "graph adapter not wired yet") -> None:
        self._reason = reason

    async def infer_diseases(self, symptoms: Sequence[str]) -> Sequence[Mapping[str, Any]]:
        raise RuntimeError(self._reason)

    async def full_graph(self) -> Mapping[str, Any]:
        raise RuntimeError(self._reason)

    async def neighbors(
        self, entity: str, depth: int = 1
    ) -> Mapping[str, Any] | None:
        raise RuntimeError(self._reason)

    async def search_entities(self, keyword: str) -> Sequence[Mapping[str, Any]]:
        raise RuntimeError(self._reason)

    async def disease_detail(self, name: str) -> Mapping[str, Any] | None:
        raise RuntimeError(self._reason)

    async def node_counts(self) -> Mapping[str, int]:
        raise RuntimeError(self._reason)


class UnavailableRetrievalPort:
    """An explicitly unwired retrieval branch; it degrades (SPEC.md 3.6). The
    running default is the Chroma adapter (`adapters.build_vector_store`,
    TICKET-013)."""

    def __init__(self, reason: str = "retrieval adapter not wired yet") -> None:
        self._reason = reason

    async def search(self, query: str, top_k: int = 5) -> Sequence[Mapping[str, Any]]:
        raise RuntimeError(self._reason)


class UnavailableLlmPort:
    """The default until a real adapter exists: generation cannot degrade, so the
    stream ends with an `error` frame (SPEC.md 3.6 / 5.5)."""

    def __init__(self, reason: str = "llm adapter not wired yet") -> None:
        self._reason = reason

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        raise RuntimeError(self._reason)
        yield ""  # pragma: no cover - keeps this an async generator
