"""幂等的图谱灌数路径（TICKET-013，`scripts/init_graph.py` 的核心）。

「不存在才创建、存在则合并」——即 Neo4j 的 `MERGE` 语义：重复执行不新增、
不删除（`FUNCTIONAL_SPEC.md` 6.7）。本模块按标签 / 关系类型分组，使每个存储
操作只开一次异步会话，避免逐条语句耗尽连接池（`SPEC.md` 3.1）。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from graph.ontology import NODE_LABELS, NODES, RELATIONSHIPS
from graph.store import GraphStats, GraphStore


@dataclass(frozen=True)
class SeedReport:
    """一次灌数的结果：写入的节点/关系条数与灌完后的图谱统计。"""

    nodes_merged: int
    relationships_merged: int
    stats: GraphStats


def _nodes_by_label() -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for label, name in NODES:
        grouped[label].append(name)
    return grouped


def _edges_by_type() -> dict[tuple[str, str, str], list[tuple[str, str]]]:
    grouped: dict[tuple[str, str, str], list[tuple[str, str]]] = defaultdict(list)
    for rel_type, start_label, start_name, end_label, end_name in RELATIONSHIPS:
        grouped[(rel_type, start_label, end_label)].append((start_name, end_name))
    return grouped


async def seed_graph(store: GraphStore) -> SeedReport:
    """把本体与种子数据写入 `store`，返回写入条数与统计。幂等：可重复执行。"""
    await store.ensure_constraints(NODE_LABELS)

    nodes_merged = 0
    for label, names in _nodes_by_label().items():
        await store.merge_nodes(label, names)
        nodes_merged += len(names)

    relationships_merged = 0
    for (rel_type, start_label, end_label), edges in _edges_by_type().items():
        await store.merge_relationships(rel_type, start_label, end_label, edges)
        relationships_merged += len(edges)

    return SeedReport(
        nodes_merged=nodes_merged,
        relationships_merged=relationships_merged,
        stats=await store.stats(),
    )
