"""图谱视图载荷的纯投影（TICKET-016）。

把适配器取回的原始行（节点的 `name`/`labels`，关系的两端与 `type`）投射成
契约里的节点/边形状：节点是 `{id, name, label}`，边是 `{source, target, type}`，
其中 `id` 由「主标签 + 名称」唯一确定。这里只有纯 CPU，不访问驱动，因此载荷
形状可以在不启动 Neo4j 的前提下被单独断言（SPEC.md 4.1 B-3）。

「科室缺失归一为 null」直接复用 graph-inference 的 `normalize_department`，
避免这条规则出现第二份实现（SPEC.md 3.6「科室缺失取值」）。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from graph.ontology import NODE_LABELS
from skills.graph_inference.inference import normalize_department

UNKNOWN_LABEL = "Unknown"


def primary_label(labels: Sequence[str]) -> str:
    """A node's display label: the first ontology label it carries."""
    for label in NODE_LABELS:
        if label in labels:
            return label
    return labels[0] if labels else UNKNOWN_LABEL


def node_id(label: str, name: str) -> str:
    return f"{label}:{name}"


def node_of(name: str, labels: Sequence[str]) -> dict[str, str]:
    label = primary_label(labels)
    return {"id": node_id(label, name), "name": name, "label": label}


def edge_of(
    rel_type: str,
    source_name: str,
    source_labels: Sequence[str],
    target_name: str,
    target_labels: Sequence[str],
) -> dict[str, str]:
    return {
        "source": node_id(primary_label(source_labels), source_name),
        "target": node_id(primary_label(target_labels), target_name),
        "type": rel_type,
    }


def _labels_of(row: Mapping[str, Any]) -> list[str]:
    labels = row.get("labels") or []
    return [str(label) for label in labels]


def node_from_row(row: Mapping[str, Any]) -> dict[str, str]:
    return node_of(str(row["name"]), _labels_of(row))


def edge_from_row(row: Mapping[str, Any]) -> dict[str, str]:
    return edge_of(
        str(row["rel_type"]),
        str(row["source_name"]),
        _labels_of({"labels": row.get("source_labels")}),
        str(row["target_name"]),
        _labels_of({"labels": row.get("target_labels")}),
    )


def graph_view(
    node_rows: Sequence[Mapping[str, Any]],
    edge_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Nodes (deduplicated, first-seen order) plus edges, for `GET /graph`."""
    nodes: dict[str, dict[str, str]] = {}
    for row in node_rows:
        node = node_from_row(row)
        nodes[node["id"]] = node
    return {
        "nodes": list(nodes.values()),
        "edges": [edge_from_row(row) for row in edge_rows],
    }


def disease_detail_payload(
    name: str,
    department: object,
    relation_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """A disease node, its department and its outgoing relations."""
    root = node_of(name, ["Disease"])
    nodes: dict[str, dict[str, str]] = {root["id"]: root}
    edges: list[dict[str, str]] = []
    for row in relation_rows:
        target = node_from_row(row)
        nodes[target["id"]] = target
        edges.append(
            {
                "source": root["id"],
                "target": target["id"],
                "type": str(row["rel_type"]),
            }
        )
    return {
        "disease": name,
        "department": normalize_department(department),
        "nodes": list(nodes.values()),
        "edges": edges,
    }
