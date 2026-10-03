"""向量索引的窄端口（TICKET-013）。

灌数与向量检索都只依赖这个协议：`add_chunks` / `delete_by_file_id` /
`count_by_file_id` 供知识库生命周期使用，`search` 就是 B-3 的 `RetrievalPort`
（`skills/ports.py`）。真实适配器 `rag/chroma_adapter.py` 同时实现两者。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class VectorStore(Protocol):
    async def add_chunks(
        self, *, file_id: int, file_name: str, chunks: Sequence[str]
    ) -> int: ...

    async def delete_by_file_id(self, file_id: int) -> None: ...

    async def count_by_file_id(self, file_id: int) -> int: ...

    async def search(
        self, query: str, top_k: int = 5
    ) -> Sequence[Mapping[str, Any]]: ...
