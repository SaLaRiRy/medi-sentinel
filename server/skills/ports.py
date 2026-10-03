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
