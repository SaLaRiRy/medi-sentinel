"""TICKET-013: the graph ontology and the idempotent seeding path.

Spec source: FUNCTIONAL_SPEC.md 2.4 / 6.2 (6 node labels, 7 relationship
types) and 6.7 (`init_graph.py` is idempotent: "repeat runs add nothing and
delete nothing"). The seed runs against an in-memory `GraphStore` so it needs
no Neo4j (SPEC.md 4.1 B-3: the real driver is an edge adapter).
"""

from collections.abc import Sequence

from graph.ontology import NODE_LABELS, NODES, RELATIONSHIPS, RELATIONSHIP_TYPES
from graph.seed import seed_graph
from graph.store import GraphStats


class InMemoryGraphStore:
    """The smallest store that keeps node/edge identity, so a second seed run
    can be proven to change nothing (merge semantics, no deletes)."""

    def __init__(self) -> None:
        self.constraints: set[str] = set()
        self.nodes: set[tuple[str, str]] = set()
        self.edges: set[tuple[str, str, str, str, str]] = set()

    async def ensure_constraints(self, labels: Sequence[str]) -> None:
        self.constraints.update(labels)

    async def merge_nodes(self, label: str, names: Sequence[str]) -> None:
        for name in names:
            self.nodes.add((label, name))

    async def merge_relationships(
        self,
        rel_type: str,
        start_label: str,
        end_label: str,
        edges: Sequence[tuple[str, str]],
    ) -> None:
        for start_name, end_name in edges:
            self.edges.add((rel_type, start_label, start_name, end_label, end_name))

    async def stats(self) -> GraphStats:
        return GraphStats(
            nodes_by_label=_counts(label for label, _ in self.nodes),
            relationships_by_type=_counts(rel for rel, *_ in self.edges),
        )


def _counts(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def test_ontology_declares_the_six_node_labels_and_seven_relationship_types():
    assert set(NODE_LABELS) == {
        "Disease",
        "Symptom",
        "Department",
        "Drug",
        "Check",
        "Food",
    }
    assert set(RELATIONSHIP_TYPES) == {
        "HAS_SYMPTOM",
        "BELONGS_TO",
        "RECOMMEND_DRUG",
        "NEED_CHECK",
        "ACCOMPANY_WITH",
        "SHOULD_EAT",
        "AVOID_EAT",
    }


def test_the_seed_covers_three_diseases_and_every_node_and_relationship_type():
    diseases = {name for label, name in NODES if label == "Disease"}
    assert {"高血压", "感冒", "糖尿病"} <= diseases

    seeded_labels = {label for label, _ in NODES}
    seeded_rels = {rel for rel, *_ in RELATIONSHIPS}
    assert seeded_labels == set(NODE_LABELS)
    assert seeded_rels == set(RELATIONSHIP_TYPES)


async def test_seed_writes_exactly_the_declared_nodes_and_relationships():
    store = InMemoryGraphStore()

    report = await seed_graph(store)

    assert store.constraints == set(NODE_LABELS)
    assert store.nodes == set(NODES)
    assert store.edges == set(RELATIONSHIPS)
    assert report.stats.total_nodes == len(NODES)
    assert report.stats.total_relationships == len(RELATIONSHIPS)
    assert set(report.stats.nodes_by_label) == set(NODE_LABELS)
    assert set(report.stats.relationships_by_type) == set(RELATIONSHIP_TYPES)


async def test_second_seed_run_adds_nothing_and_deletes_nothing():
    store = InMemoryGraphStore()
    await seed_graph(store)
    after_first_nodes = set(store.nodes)
    after_first_edges = set(store.edges)

    report = await seed_graph(store)

    assert store.nodes == after_first_nodes
    assert store.edges == after_first_edges
    assert report.stats.total_nodes == len(NODES)
    assert report.stats.total_relationships == len(RELATIONSHIPS)
