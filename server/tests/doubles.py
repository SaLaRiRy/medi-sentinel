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


class StubLlmPort:
    async def stream(self, prompt: str) -> AsyncIterator[str]:
        yield ""
