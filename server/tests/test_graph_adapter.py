"""TICKET-013 挂账：真实异步图库适配器（`AsyncGraphDatabase`）。

The driver is not installed here, so importing the module must not import it
(the adapter is an edge adapter, SPEC.md 4.1 B-3). Its Cypher is exercised
through an injected fake driver, so the queries are asserted without a server.
"""

import re
from pathlib import Path
from typing import Any

import pytest

from graph import neo4j_adapter
from graph.neo4j_adapter import Neo4jGraphAdapter
from graph.ontology import NODE_LABELS
from graph.store import GraphStats, GraphStore
from skills.ports import GraphPort

SERVER_ROOT = Path(__file__).resolve().parents[1]


class FakeResult:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self._data = data

    async def data(self) -> list[dict[str, Any]]:
        return list(self._data)


class FakeSession:
    def __init__(self, log: list[tuple[str, dict]], responses: list[list[dict]]) -> None:
        self._log = log
        self._responses = responses

    async def run(self, query: str, **params: Any) -> FakeResult:
        self._log.append((query, params))
        return FakeResult(self._responses.pop(0) if self._responses else [])

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


class FakeDriver:
    """Records every Cypher statement and replays canned rows in order."""

    def __init__(self, responses: list[list[dict]] | None = None) -> None:
        self.log: list[tuple[str, dict]] = []
        self.responses = list(responses or [])
        self.closed = False

    def session(self, database: str | None = None) -> FakeSession:
        return FakeSession(self.log, self.responses)

    async def close(self) -> None:
        self.closed = True


def adapter_with(*responses: list[dict]) -> tuple[Neo4jGraphAdapter, FakeDriver]:
    driver = FakeDriver(list(responses))
    adapter = Neo4jGraphAdapter(
        "bolt://127.0.0.1:7687", "neo4j", "secret", driver=driver
    )
    return adapter, driver


def test_the_adapter_module_imports_without_the_neo4j_driver_installed():
    # Collection already imported it; assert it did not pull the real driver in.
    assert neo4j_adapter is not None
    assert "neo4j" not in getattr(neo4j_adapter, "__dict__", {})


def test_the_adapter_satisfies_the_graph_port_and_store_contracts():
    adapter, _ = adapter_with()

    assert isinstance(adapter, GraphPort)
    assert isinstance(adapter, GraphStore)


def test_the_adapter_uses_the_async_driver_only():
    source = (SERVER_ROOT / "graph" / "neo4j_adapter.py").read_text(encoding="utf-8")

    assert "AsyncGraphDatabase" in source
    # The same rule AC-B-24 scans for: a bare `GraphDatabase` is the sync driver.
    assert re.search(r"(?<!Async)GraphDatabase\b", source) is None


def test_requirements_declare_the_neo4j_driver():
    requirements = (SERVER_ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert any(line.strip().startswith("neo4j") for line in requirements.splitlines())


async def test_ensure_constraints_creates_one_uniqueness_constraint_per_label():
    adapter, driver = adapter_with()

    await adapter.ensure_constraints(NODE_LABELS)

    statements = [query for query, _ in driver.log]
    assert len(statements) == len(NODE_LABELS)
    assert all("CREATE CONSTRAINT" in query for query in statements)
    assert all("IF NOT EXISTS" in query for query in statements)
    assert all("IS UNIQUE" in query for query in statements)
    for label in NODE_LABELS:
        assert any(f":`{label}`" in query for query in statements)


async def test_merge_nodes_writes_one_unwind_merge_statement():
    adapter, driver = adapter_with()

    await adapter.merge_nodes("Symptom", ["头痛", "发热"])

    query, params = driver.log[-1]
    assert "UNWIND $names AS name" in query
    assert "MERGE (n:`Symptom` {name: name})" in query
    assert params == {"names": ["头痛", "发热"]}


async def test_merge_relationships_matches_both_ends_then_merges_the_edge():
    adapter, driver = adapter_with()

    await adapter.merge_relationships(
        "HAS_SYMPTOM", "Disease", "Symptom", [("感冒", "发热")]
    )

    query, params = driver.log[-1]
    assert "MATCH (a:`Disease` {name: edge[0]})" in query
    assert "MATCH (b:`Symptom` {name: edge[1]})" in query
    assert "MERGE (a)-[:`HAS_SYMPTOM`]->(b)" in query
    assert params == {"edges": [["感冒", "发热"]]}


async def test_unknown_labels_are_rejected_before_reaching_cypher():
    adapter, driver = adapter_with()

    with pytest.raises(ValueError):
        await adapter.merge_nodes("Symptom`) DETACH DELETE n //", ["头痛"])

    assert driver.log == []


async def test_infer_diseases_maps_the_query_rows_to_disease_records():
    rows = [
        {
            "disease": "感冒",
            "matched_symptoms": ["发热", "头痛"],
            "department": "呼吸内科",
        }
    ]
    adapter, driver = adapter_with(rows)

    records = await adapter.infer_diseases(["头痛", "发热"])

    query, params = driver.log[-1]
    assert "HAS_SYMPTOM" in query and "BELONGS_TO" in query
    assert params == {"symptoms": ["头痛", "发热"]}
    assert records == rows


async def test_stats_aggregates_nodes_by_label_and_relationships_by_type():
    node_rows = [{"label": "Disease", "count": 3}, {"label": "Symptom", "count": 19}]
    rel_rows = [{"rel_type": "HAS_SYMPTOM", "count": 18}]
    adapter, _ = adapter_with(node_rows, rel_rows)

    stats = await adapter.stats()

    assert stats == GraphStats(
        nodes_by_label={"Disease": 3, "Symptom": 19},
        relationships_by_type={"HAS_SYMPTOM": 18},
    )
    assert stats.total_nodes == 22
    assert stats.total_relationships == 18


async def test_close_releases_the_driver():
    adapter, driver = adapter_with()

    await adapter.close()

    assert driver.closed
