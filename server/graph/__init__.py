"""医学知识图谱：本体定义、幂等灌数路径与 Neo4j 异步适配器（TICKET-013）。

图谱查询仍走 B-3 的 `GraphPort`（`skills/ports.py`）；本包提供它背后的真实存储：

- `ontology` —— 6 类节点与 7 类关系的本体与种子数据（`FUNCTIONAL_SPEC.md` 2.4 / 6.2）；
- `seed` —— 幂等灌数逻辑（`scripts/init_graph.py` 的核心，可在内存假实现上测试）；
- `neo4j_adapter` —— 基于 `AsyncGraphDatabase` 的真实异步适配器（`SPEC.md` 3.1）。
"""
