"""Neo4j 异步图库适配器（TICKET-013）。

这是 `graph-inference` SKILL.md §1.3 承诺的「查询必须走 Neo4j 异步驱动」的落地：
所有查询都经 `AsyncGraphDatabase`（`SPEC.md` 3.1），每次调用开一个异步会话，
由驱动在事务提交/回滚后归还连接池。驱动按需导入，模块本身不依赖它 —— 这样在没有
安装 `neo4j` 的环境里仍可导入、单测与降级（`skills.ports.GraphPort`）。

本类同时实现 B-3 的 `GraphPort`（供 graph-inference 调用）与灌数用的 `GraphStore`
（`scripts/init_graph.py`）。所有写入都是 `MERGE`，重复执行不新增、不删除
（`FUNCTIONAL_SPEC.md` 6.7）。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Mapping

from graph.ontology import NODE_LABELS, RELATIONSHIP_TYPES
from graph.store import GraphStats

# 实体邻域子图的关系条数上限（`FUNCTIONAL_SPEC.md` 2.4 `get_entity_subgraph`）。
MAX_NEIGHBORS = 30
MAX_DEPTH = 5

_NODE_COUNTS = "MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS count"
_REL_COUNTS = "MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS count"


def _require_label(label: str) -> None:
    if label not in NODE_LABELS:
        raise ValueError(f"未知的节点标签：{label!r}")


def _require_relationship(rel_type: str) -> None:
    if rel_type not in RELATIONSHIP_TYPES:
        raise ValueError(f"未知的关系类型：{rel_type!r}")


def _require_depth(depth: int) -> int:
    if (
        not isinstance(depth, int)
        or isinstance(depth, bool)
        or not 1 <= depth <= MAX_DEPTH
    ):
        raise ValueError(f"depth 必须是 1..{MAX_DEPTH} 之间的整数：{depth!r}")
    return depth


class Neo4jGraphAdapter:
    """`AsyncGraphDatabase` 之上的图端口与灌数端口。"""

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        *,
        database: str | None = None,
        driver: Any | None = None,
    ) -> None:
        self._uri = uri
        self._user = user
        self._password = password
        self._database = database
        self._driver = driver

    @property
    def driver(self) -> Any:
        if self._driver is None:
            from neo4j import AsyncGraphDatabase

            self._driver = AsyncGraphDatabase.driver(
                self._uri, auth=(self._user, self._password)
            )
        return self._driver

    async def _run(self, query: str, **params: Any) -> list[dict[str, Any]]:
        """每次一个异步会话；会话结束即提交/回滚并把连接归还连接池。"""
        async with self.driver.session(database=self._database) as session:
            result = await session.run(query, **params)
            return [dict(record) for record in await result.data()]

    async def close(self) -> None:
        if self._driver is not None:
            await self._driver.close()

    # --- 灌数端口（GraphStore） -------------------------------------------------

    async def ensure_constraints(self, labels: Sequence[str]) -> None:
        for label in labels:
            _require_label(label)
            name = f"uniq_{label.lower()}_name"
            statement = (
                f"CREATE CONSTRAINT {name} IF NOT EXISTS "
                f"FOR (n:`{label}`) REQUIRE n.name IS UNIQUE"
            )
            try:
                await self._run(statement)
            except Exception:
                # 约束已存在/权限不足等被静默忽略（FUNCTIONAL_SPEC.md 6.7）。
                continue

    async def merge_nodes(self, label: str, names: Sequence[str]) -> None:
        _require_label(label)
        await self._run(
            f"UNWIND $names AS name MERGE (n:`{label}` {{name: name}})",
            names=list(names),
        )

    async def merge_relationships(
        self,
        rel_type: str,
        start_label: str,
        end_label: str,
        edges: Sequence[tuple[str, str]],
    ) -> None:
        _require_relationship(rel_type)
        _require_label(start_label)
        _require_label(end_label)
        await self._run(
            "UNWIND $edges AS edge "
            f"MATCH (a:`{start_label}` {{name: edge[0]}}) "
            f"MATCH (b:`{end_label}` {{name: edge[1]}}) "
            f"MERGE (a)-[:`{rel_type}`]->(b)",
            edges=[[start, end] for start, end in edges],
        )

    async def stats(self) -> GraphStats:
        nodes = await self._run(_NODE_COUNTS)
        relationships = await self._run(_REL_COUNTS)
        return GraphStats(
            nodes_by_label={str(row["label"]): int(row["count"]) for row in nodes},
            relationships_by_type={
                str(row["rel_type"]): int(row["count"]) for row in relationships
            },
        )

    # --- 查询端口（GraphPort） --------------------------------------------------

    async def infer_diseases(
        self, symptoms: Sequence[str]
    ) -> Sequence[Mapping[str, Any]]:
        """沿「疾病-有症状-症状」反查，连带取出所属科室（`FUNCTIONAL_SPEC.md` 5.3）。

        端口只负责取回记录，命中数统计、覆盖率、排序与截断由 graph-inference 完成。
        """
        return await self._run(
            "MATCH (d:Disease)-[:HAS_SYMPTOM]->(s:Symptom) "
            "WHERE s.name IN $symptoms "
            "OPTIONAL MATCH (d)-[:BELONGS_TO]->(dept:Department) "
            "RETURN d.name AS disease, "
            "collect(DISTINCT s.name) AS matched_symptoms, "
            "dept.name AS department",
            symptoms=list(symptoms),
        )

    async def neighbors(self, entity: str, depth: int = 1) -> Mapping[str, Any]:
        """实体邻域子图，`depth` 真实生效（`SPEC.md` 3.6「无无效参数」）。"""
        validated = _require_depth(depth)
        rows = await self._run(
            "MATCH (n {name: $entity}) "
            f"OPTIONAL MATCH (n)-[rels*1..{validated}]->(m) "
            "WITH n, m, rels WHERE m IS NOT NULL "
            "RETURN m.name AS name, labels(m) AS labels, "
            "[rel IN rels | type(rel)] AS rel_types "
            "ORDER BY name "
            f"LIMIT {MAX_NEIGHBORS}",
            entity=entity,
        )
        return {"entity": entity, "depth": validated, "neighbors": rows}
