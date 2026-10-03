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
from graph.query import (
    disease_detail_payload,
    edge_from_row,
    graph_view,
    node_from_row,
)
from graph.store import GraphStats

# 实体邻域子图的关系条数上限（`FUNCTIONAL_SPEC.md` 2.4 `get_entity_subgraph`）。
MAX_NEIGHBORS = 30
MAX_DEPTH = 5
# 实体搜索条数上限（`FUNCTIONAL_SPEC.md` 2.4 `search_entities`）。
SEARCH_LIMIT = 20

_NODE_COUNTS = "MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS count"
_REL_COUNTS = "MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS count"
_FULL_NODES = "MATCH (n) RETURN n.name AS name, labels(n) AS labels ORDER BY name"
_FULL_EDGES = (
    "MATCH (a)-[r]->(b) "
    "RETURN a.name AS source_name, labels(a) AS source_labels, "
    "b.name AS target_name, labels(b) AS target_labels, type(r) AS rel_type "
    "ORDER BY rel_type, source_name, target_name"
)
_SEARCH = (
    "MATCH (n) WHERE n.name CONTAINS $keyword "
    f"RETURN n.name AS name, labels(n) AS labels ORDER BY n.name LIMIT {SEARCH_LIMIT}"
)
_ENTITY = "MATCH (root {name: $entity}) RETURN root.name AS name, labels(root) AS labels"
# The Cypher contains literal `{name: $entity}` maps, so the validated depth is
# substituted through a plain token instead of `str.format` (which would read
# those braces as replacement fields).
DEPTH_TOKEN = "__DEPTH__"
_NEIGHBOUR_NODES = (
    f"MATCH (root {{name: $entity}}) MATCH (root)-[*1..{DEPTH_TOKEN}]-(m) "
    "RETURN DISTINCT m.name AS name, labels(m) AS labels "
    f"ORDER BY name LIMIT {MAX_NEIGHBORS}"
)
_NEIGHBOUR_EDGES = (
    f"MATCH (root {{name: $entity}}) MATCH (root)-[*1..{DEPTH_TOKEN}]-(m) "
    "WITH collect(DISTINCT m) + root AS nodes UNWIND nodes AS a "
    "MATCH (a)-[r]->(b) WHERE b IN nodes "
    "RETURN DISTINCT a.name AS source_name, labels(a) AS source_labels, "
    "b.name AS target_name, labels(b) AS target_labels, type(r) AS rel_type "
    f"ORDER BY rel_type, source_name, target_name LIMIT {MAX_NEIGHBORS}"
)
_DISEASE_ROOT = "MATCH (d:Disease {name: $name}) RETURN d.name AS name"
_DISEASE_DEPARTMENT = (
    "MATCH (d:Disease {name: $name}) "
    "OPTIONAL MATCH (d)-[:BELONGS_TO]->(dept:Department) "
    "RETURN dept.name AS department"
)
_DISEASE_RELATIONS = (
    "MATCH (d:Disease {name: $name})-[r]->(m) "
    "RETURN type(r) AS rel_type, m.name AS name, labels(m) AS labels "
    "ORDER BY rel_type, name"
)


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

    async def full_graph(self) -> Mapping[str, Any]:
        """全图（节点 + 有向关系），供 `GET /graph` 可视化（FUNCTIONAL_SPEC 2.4）。"""
        node_rows = await self._run(_FULL_NODES)
        edge_rows = await self._run(_FULL_EDGES)
        return graph_view(node_rows, edge_rows)

    async def neighbors(
        self, entity: str, depth: int = 1
    ) -> Mapping[str, Any] | None:
        """实体邻域子图，`depth` 真实生效；实体不存在时返回 `None`。

        `depth` 是 1..5 的整数（`_require_depth` 校验后插入已限定的 Cypher），
        返回以该实体为中心、最多 `MAX_NEIGHBORS` 个相关节点的子图
        （`SPEC.md` 3.6「无无效参数」）。
        """
        validated = _require_depth(depth)
        root_rows = await self._run(_ENTITY, entity=entity)
        if not root_rows:
            return None
        node_rows = await self._run(
            _NEIGHBOUR_NODES.replace(DEPTH_TOKEN, str(validated)), entity=entity
        )
        edge_rows = await self._run(
            _NEIGHBOUR_EDGES.replace(DEPTH_TOKEN, str(validated)), entity=entity
        )
        nodes: dict[str, dict[str, str]] = {}
        for row in [*root_rows, *node_rows]:
            node = node_from_row(row)
            nodes[node["id"]] = node
        return {
            "nodes": list(nodes.values()),
            "edges": [edge_from_row(row) for row in edge_rows],
        }

    async def search_entities(
        self, keyword: str
    ) -> Sequence[Mapping[str, Any]]:
        """按名称包含匹配的实体搜索，上限 `SEARCH_LIMIT`（FUNCTIONAL_SPEC 2.4）。"""
        rows = await self._run(_SEARCH, keyword=keyword)
        return [node_from_row(row) for row in rows]

    async def disease_detail(self, name: str) -> Mapping[str, Any] | None:
        """疾病详情子图：科室 + 全部出边；疾病不存在时返回 `None`。"""
        root_rows = await self._run(_DISEASE_ROOT, name=name)
        if not root_rows:
            return None
        department_rows = await self._run(_DISEASE_DEPARTMENT, name=name)
        relation_rows = await self._run(_DISEASE_RELATIONS, name=name)
        department = department_rows[0]["department"] if department_rows else None
        return disease_detail_payload(name, department, relation_rows)

    async def node_counts(self) -> Mapping[str, int]:
        """按标签的节点计数（`GET /graph/stats`，FUNCTIONAL_SPEC 2.4）。"""
        rows = await self._run(_NODE_COUNTS)
        return {str(row["label"]): int(row["count"]) for row in rows}
