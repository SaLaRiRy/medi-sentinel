# 02: Skill 协议与 trace 基座（剩余部分）

**What to build:** trace 基座尚未完成的部分：把 span 落到可检索的持久化存储，让一次问诊的全部 span 能按 `trace_id` 取回并按时间顺序还原；让编排记录本轮的 Skill 路由决策（执行了哪些、跳过了哪些、跳过理由）；并让 trace 汇聚的内存替身支持按 `trace_id` 回放断言。

**部分内容已由 TICKET-001 完成**，不要重复实现：

- 统一 `invoke(input) → output` 协议，以及输入输出的 Schema 校验与「校验失败不静默继续」（`skills/protocol.py`）
- 每次 Skill 调用与大模型调用恰好产生一条 span，`trace_id` 在一次问诊内全局一致（`skills/trace.py`、`skills/protocol.py`）
- 摘要长度截断：患者原文与大模型完整输出不以完整形式进入 span（`skills/trace.py` 的 `digest`）
- 三个外部资源端口协议 `GraphPort` / `RetrievalPort` / `LlmPort`（`skills/ports.py`）
- SSE 帧序与 `trace_id` 一致性（`skills/orchestration.py` 的骨架）
- trace 汇聚的内存替身基础形态：`record_span` / `record_route`（`skills/trace.py` 的 `InMemoryTraceSink`）

原票中「五个 Skill 可在不启动关系库、图库、向量索引的前提下被单独实例化并调用」一项，随五个 Skill 的落地在 TICKET-003…007 验收，不在本票范围。

**Blocked by:** 01（工程骨架与契约 seam）—— 已完成

**Status:** ready-for-agent

- [ ] 一次问诊的全部 span 可按 `trace_id` 取回，并按时间顺序还原
- [ ] span 持久化到结构化存储，可按键检索、可按时间范围聚合
- [ ] 每次编排产生一条路由决策记录，含实际执行的 Skill 列表、跳过的 Skill 列表与跳过理由
- [ ] trace 汇聚的内存替身支持按 `trace_id` 取回本轮的 span 与路由决策，可在不启动数据库的前提下完成回放断言
- [ ] span 落库时摘要仍受长度上限约束，患者原文与大模型完整输出不以完整形式落库
