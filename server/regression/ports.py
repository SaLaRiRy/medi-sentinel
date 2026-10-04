"""B-3 ports for the regression framework: recording, replay, and the judge seam.

`record` wraps the deterministic offline ports in `Recording*` adapters and keeps
every `(method, args) -> result` answer. `replay` rebuilds the three
`OrchestrationPorts` from that recording, so a consult re-runs with **zero**
external I/O (SPEC.md 3.8 / 4.4, AC-B-35).

This module is deliberately free of `adapters` / `neo4j` / `chroma` imports: a
replay must not be able to reach a real dependency even by accident.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any, Mapping, Protocol, runtime_checkable

from skills.ports import GraphPort, LlmPort, RetrievalPort, UnavailableLlmPort


@runtime_checkable
class JudgePort(Protocol):
    """The hallucination judge seam (SPEC.md 3.8, ticket 023 §4).

    `judge` answers whether one free-text `assertion` is supported by the
    `context` the answer was generated from. `available` tells the metrics layer
    whether the judge could run at all, so a missing judge degrades to
    `judged_ratio = 0.0` + `judge_available = false` instead of failing the replay.
    """

    available: bool

    async def judge(self, assertion: str, context: str) -> bool: ...


class UnavailableJudgePort:
    """The default judge: no model is wired, so the judged layer is not applied."""

    available = False

    async def judge(self, assertion: str, context: str) -> bool:
        raise RuntimeError("judge model not wired yet")


class LlmJudgePort:
    """Ask the model whether an assertion is supported by the context.

    The application default wires `UnavailableLlmPort`, so this reports
    `available = False` and the judged layer is skipped (降级不阻断).
    """

    def __init__(self, llm: LlmPort) -> None:
        self._llm = llm
        self.available = not isinstance(self._llm, UnavailableLlmPort)

    async def judge(self, assertion: str, context: str) -> bool:
        prompt = (
            "请判断下面的断言能否由参考上下文支持。只回答「有据」或「无据」。\n"
            f"参考上下文：{context}\n断言：{assertion}"
        )
        text = "".join([chunk async for chunk in self._llm.stream(prompt)])
        return "有据" in text and "无据" not in text


class RecordingGraphPort:
    """Decorator: answer like `inner` and keep every response in call order."""

    def __init__(self, inner: GraphPort) -> None:
        self._inner = inner
        self.responses: list[list[Mapping[str, Any]]] = []

    async def infer_diseases(
        self, symptoms: Sequence[str]
    ) -> Sequence[Mapping[str, Any]]:
        result = await self._inner.infer_diseases(symptoms)
        self.responses.append([dict(record) for record in result])
        return result

    async def full_graph(self) -> Mapping[str, Any]:
        return await self._inner.full_graph()

    async def neighbors(self, entity: str, depth: int = 1) -> Mapping[str, Any] | None:
        return await self._inner.neighbors(entity, depth)

    async def search_entities(self, keyword: str) -> Sequence[Mapping[str, Any]]:
        return await self._inner.search_entities(keyword)

    async def disease_detail(self, name: str) -> Mapping[str, Any] | None:
        return await self._inner.disease_detail(name)

    async def node_counts(self) -> Mapping[str, int]:
        return await self._inner.node_counts()


class RecordingRetrievalPort:
    """Decorator: answer like `inner` and keep every response in call order."""

    def __init__(self, inner: RetrievalPort) -> None:
        self._inner = inner
        self.responses: list[list[Mapping[str, Any]]] = []

    async def search(
        self, query: str, top_k: int = 5
    ) -> Sequence[Mapping[str, Any]]:
        result = await self._inner.search(query, top_k)
        self.responses.append([dict(hit) for hit in result])
        return result


class RecordingLlmPort:
    """Decorator: stream like `inner` and keep each call's chunk list."""

    def __init__(self, inner: LlmPort) -> None:
        self._inner = inner
        self.chunks: list[list[str]] = []

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        produced: list[str] = []
        async for chunk in self._inner.stream(prompt):
            produced.append(chunk)
            yield chunk
        self.chunks.append(produced)


class ReplayGraphPort:
    """Answer `infer_diseases` from the recorded responses, in order."""

    def __init__(self, responses: Sequence[Sequence[Mapping[str, Any]]]) -> None:
        self._queue = [list(response) for response in responses]
        self._cursor = 0

    async def infer_diseases(
        self, symptoms: Sequence[str]
    ) -> Sequence[Mapping[str, Any]]:
        if self._cursor >= len(self._queue):
            raise RuntimeError("回放端口：录制的图谱响应已用尽（本次问诊比录制时多调用了图谱）")
        response = self._queue[self._cursor]
        self._cursor += 1
        return response

    async def full_graph(self) -> Mapping[str, Any]:
        raise RuntimeError("回放不访问图库读取接口")

    async def neighbors(self, entity: str, depth: int = 1) -> Mapping[str, Any] | None:
        raise RuntimeError("回放不访问图库读取接口")

    async def search_entities(self, keyword: str) -> Sequence[Mapping[str, Any]]:
        raise RuntimeError("回放不访问图库读取接口")

    async def disease_detail(self, name: str) -> Mapping[str, Any] | None:
        raise RuntimeError("回放不访问图库读取接口")

    async def node_counts(self) -> Mapping[str, int]:
        raise RuntimeError("回放不访问图库读取接口")


class ReplayRetrievalPort:
    """Answer `search` from the recorded responses, in order."""

    def __init__(self, responses: Sequence[Sequence[Mapping[str, Any]]]) -> None:
        self._queue = [list(response) for response in responses]
        self._cursor = 0

    async def search(
        self, query: str, top_k: int = 5
    ) -> Sequence[Mapping[str, Any]]:
        if self._cursor >= len(self._queue):
            raise RuntimeError("回放端口：录制的检索响应已用尽（本次问诊比录制时多调用了检索）")
        response = self._queue[self._cursor]
        self._cursor += 1
        return response


class ReplayLlmPort:
    """Re-emit the recorded chunk sequences, one call at a time."""

    def __init__(self, chunks: Sequence[Sequence[str]]) -> None:
        self._queue = [list(chunks_for_call) for chunks_for_call in chunks]
        self._cursor = 0

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        if self._cursor >= len(self._queue):
            raise RuntimeError("回放端口：录制的大模型响应已用尽（本次问诊比录制时多调用了大模型）")
        chunks = self._queue[self._cursor]
        self._cursor += 1
        for chunk in chunks:
            yield chunk
