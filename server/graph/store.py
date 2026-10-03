"""图谱存储的窄端口（TICKET-013）。

灌数逻辑（`graph/seed.py`）只依赖这个协议，不依赖 Neo4j 驱动，因此可用内存
假实现验证幂等性（`SPEC.md` 4.1 B-3：真实驱动属基础设施，测试替换为假实现）。
真实适配器 `graph/neo4j_adapter.py` 同时实现本协议与 `skills.ports.GraphPort`。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class GraphStats:
    """按标签与关系类型的数量统计（`FUNCTIONAL_SPEC.md` 2.4 `get_graph_stats`）。"""

    nodes_by_label: Mapping[str, int] = field(default_factory=dict)
    relationships_by_type: Mapping[str, int] = field(default_factory=dict)

    @property
    def total_nodes(self) -> int:
        return sum(self.nodes_by_label.values())

    @property
    def total_relationships(self) -> int:
        return sum(self.relationships_by_type.values())


@runtime_checkable
class GraphStore(Protocol):
    """灌数所需的写路径：约束、按标签合并节点、按关系类型合并边、统计。"""

    async def ensure_constraints(self, labels: Sequence[str]) -> None: ...

    async def merge_nodes(self, label: str, names: Sequence[str]) -> None: ...

    async def merge_relationships(
        self,
        rel_type: str,
        start_label: str,
        end_label: str,
        edges: Sequence[tuple[str, str]],
    ) -> None: ...

    async def stats(self) -> GraphStats: ...
