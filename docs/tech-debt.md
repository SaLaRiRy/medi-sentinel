# 技术债清单

记录已识别、但**经决策延后**的技术债。每条注明来源、影响与建议的处理时机；
处理时机一到，就把条目移到对应票并从此处删除。

## 待处理

| # | 来源 | 内容 | 建议时机 |
|---|---|---|---|
| 1 | TICKET-016 审查 | `server/api/v1/graph.py` 从具体适配器 `graph.neo4j_adapter` 导入 `MAX_DEPTH`，HTTP 层为一处边界值耦合到基础设施层。抽 `graph/limits.py`（或放进 ontology）作为中立常量来源。 | TICKET-011 相关重构时 |
| 2 | TICKET-016 审查 | `graph/query.py` 的 `edge_from_row` 用 `_labels_of({"labels": row.get("source_labels")})` 合成一个假映射再解包，读起来绕。让 `_labels_of` 直接接收标签序列。 | 下一次触碰 `graph/query.py` 时 |
| 3 | TICKET-016 审查 | `server/core/contract.py` 无条件把 `Envelope_NoneType_` 组件注入契约，即使没有任何端点引用它。改为仅在确实需要时注入，或复用 FastAPI 已生成的同名组件。 | 下一次触碰契约生成时 |
| 4 | TICKET-016 审查 | `SymptomView.vue` 与 `ChatView.vue` 的候选疾病列表标记重复（`candidates.js` 只抽了逻辑）。把候选列表抽成一个共享组件（或至少共享一段模板片段）。 | 下一次触碰任一候选列表时 |
| 5 | TICKET-016 审查 | AC-B-41「每个端点的实际响应均满足契约 Schema（含成功与全部错误码分支）」：新端点已声明全部错误分支，但 AC-B-41 的完整覆盖面仍需统一补齐与校验。 | TICKET-024（验收回归）统一补 |
| 6 | TICKET-016 审查 | 007–015 的既有端点仍只声明 200 + 422（422 的形状已在 TICKET-016 的 chore 中全局修正），尚未声明各自的 401/403/404/409/413/503/504 分支。 | TICKET-024 统一补 |
| 7 | TICKET-016 审查 | `SPEC.md` §5.3 的 Schema 索引未定义 `GraphView` / `GraphEntityView` / `DiseaseDetailView`（当前形状由实现自定）。把这些 schema 补进 §5.3。 | 补充 SPEC 时 |
| 8 | TICKET-AC-11/12 复盘 | `diagnosis_drift_rate` 在**回放路径上是恒真式**：`regression/replay.py:174` 的 `baseline_candidates` 与回放候选都取自同一份基线，必然相等，`regression/metrics.py:247` 于是恒得 0——**代码改坏也报 0**（实测 v1 与 v3 的候选在 12/20 条上不同，两边仍报 0.0）。该指标只在 **record 路径**上有意义。 | 下次要动回放语义时——修它必须让回放**重新执行**（而非喂回录制数据），会与 AC-B-35「回放零外部依赖」冲突，需两者一起重新设计 |

## 已接受（明确不处理）

| # | 来源 | 内容 | 决策 |
|---|---|---|---|
| A | TICKET-016 审查 | `graph/query.py` 反向依赖 `skills.graph_inference.inference.normalize_department`（存储层依赖 Skill 层）。 | 保留：SPEC §3.6 授权「科室缺失归一为 `null`」只有一份实现，共享该纯函数优于复制规则。 |
| B | TICKET-016 审查 | `client/src/api/client.js` 的 `graphStats()` 目前没有视图消费者（仅契约测试调用）。 | 保留：`GET /graph/stats` 是 `SPEC.md` §5.4 规定的端点，F-1 出口按契约完整暴露。 |
| C | TICKET-AC-12 | 字面判定层**覆盖率仅 32%**：v3 的 1267 条非空断言里只有 400 条含可判定 token；未评估的 867 条中大量是「就医 / 急诊 / 警惕 / 尽快」类安全提示，而 `_DETERMINISTIC_TERMS` 只有疾病 / 药品 / 检查节点名与数字。 | 接受（用户 2026-10-11 拍板选 (b)）：把该层明确记为「低覆盖率、价格低廉的初筛」，覆盖率写进 `.scratch/agentic-consult/METRICS.md`，比率**不对外引用**。提高覆盖率的正路（接上从未接线的 `LlmJudgePort`）记为 **AC-13 占位**，不在本轮做。 |
| D | TICKET-AC-10 | `baselines/v3.json` 是**不可复现的真实调用快照**（模型每次回答不同），体积 972 KB / 20 条。 | 接受：SPEC 3.8 要求基线随版本控制流转，972 KB 对 git 无压力；回放逐字稳定（chunk 已录），`evidence_match_rate` 与 `replay --compare` 不受影响。**总大小超过约 5 MB 时再考虑压缩**（优先去掉 `llm_chunks` 与 `frames` 里 content 帧的重复文本）。 |
| E | TICKET-AC-04 | 本地 ONNX 重排对 `recall@1` 与 `MRR` **零提升**（RRF 融合已把首条命中文档排在第 1 位），只把多标签用例 q13 的第二篇拉回 top-5（recall@5 +1/30），代价约 **+1.24 s/次**。 | 接受：默认关闭（`RERANK_MODEL_DIR` 留空），需要时按环境开启；实测配置扫描见票 04。 |
