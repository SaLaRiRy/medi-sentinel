"""B-3: the three narrow ports. They exist so tests can count calls — above all,
so "the LLM was not called" is assertable (SPEC.md 4.1, 4.5)."""

from collections.abc import AsyncIterator, Sequence
from typing import Any, Mapping, Protocol, runtime_checkable


@runtime_checkable
class GraphPort(Protocol):
    async def infer_diseases(self, symptoms: Sequence[str]) -> Sequence[Mapping[str, Any]]: ...

    async def neighbors(self, entity: str, depth: int = 1) -> Mapping[str, Any]: ...


@runtime_checkable
class RetrievalPort(Protocol):
    async def search(self, query: str, top_k: int = 5) -> Sequence[Mapping[str, Any]]: ...


@runtime_checkable
class LlmPort(Protocol):
    def stream(self, prompt: str) -> AsyncIterator[str]: ...


class UnavailableGraphPort:
    """The default until a real adapter exists: the graph branch degrades instead
    of the process crashing (SPEC.md 3.6). The Neo4j `AsyncGraphDatabase` adapter
    lands with the store it talks to (TICKET-013)."""

    def __init__(self, reason: str = "graph adapter not wired yet") -> None:
        self._reason = reason

    async def infer_diseases(self, symptoms: Sequence[str]) -> Sequence[Mapping[str, Any]]:
        raise RuntimeError(self._reason)

    async def neighbors(self, entity: str, depth: int = 1) -> Mapping[str, Any]:
        raise RuntimeError(self._reason)


class UnavailableRetrievalPort:
    """The default until a real adapter exists; the retrieval branch degrades
    (SPEC.md 3.6)."""

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
