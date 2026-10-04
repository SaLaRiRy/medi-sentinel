"""回归基线框架（TICKET-023，SPEC.md 3.8 / 4.4）。

一处能力、两条命令：`record` 用确定性端口离线录制版本化基线，`replay` 只读基线
重建一次问诊并输出 `MetricsReport`。回放全程不访问图库、向量索引、嵌入服务与
大模型（AC-B-35）——本包只依赖 `skills/` 的端口协议，不 import `adapters` /
`neo4j` / `chroma`。
"""
