# map —— agentic-consult

**Effort**：MediSentinel「检索增强 · 业务闭环 · 降级容错」改造。
**规格**：[spec.md](spec.md)（范围、硬约束、偏离纪律、未决项）。
**票据约定**：一票一文件 `issues/NN-<slug>.md`；`Blocked by:` 行声明依赖；`Status:` 行记录状态。

## 前沿（Frontier）

| 票 | 状态 | 说明 |
|---|---|---|
| 01 扩知识库 | ready-for-agent | 第一票，无依赖。票 03/04 的地基 |
| 05 闭环 A | ready-for-agent | 与 01–04 独立，可并行 |
| 08 降级容错 | ready-for-agent | 与其余各票独立 |

`02 ← 01`、`03 ← 01`、`04 ← 02,03`、`06 ← 05`、`07 ← 06`、`09 ← 08`。

## Decisions so far

1. **执行顺序 = 票号**：01 扩库 → 02 混合检索 → 03 评测集 → 04 ONNX 重排 → 05 闭环 A →
   06 闭环 B → 07 闭环 C → 08 降级容错 →（可选）09 LangChain。
2. **先扩库再评测**：活库 `t_knowledge_chunk = 3` 而 `RETRIEVAL_TOP_K = 5`，
   池子不足时 `recall@5` 恒等于 100%，评测数字没有信息量（→ 票 01 是第一票）。
3. **重排走 ONNX 不走 torch**：`onnxruntime 1.30.0` 与 `tokenizers` 已在 `.venv`；
   `onnx/model.onnx` 1112.5 MB 自带权重、单文件；单对 29.8 ms（→ 票 04）。
4. **闭环反哺走串行预取传值**，不新建 `PatientContextPort`——避免同时踩
   `OrchestrationPorts` 22 个构造点、`gather` 位置索引、回放 FIFO 三处雷（→ 票 07）。
5. **新能力优先放进既有端口的实现层**，让编排层调用序列不变——这样录制/回放、
   `tests/doubles.py`、baseline 都不用动（→ 票 02 的 RRF、票 04 的首选方案 A）。
6. **`regression/divergences.py:19` 的正则只认 `A-*` / `H-*`**：开新族必须同改正则，
   否则新登记的有意偏离被静默忽略、不被回归豁免（→ spec.md 4.6，票 07）。
7. **`server/.tmp` 的 27 个 ACL 拒绝访问目录已清理**，`server/_probe_live.py` 与
   `server/_probe_rerank.py` 两个探针已删除；仓库根递归搜索恢复正常（2026-10-11 开工前置）。
8. **`S-*` = 独立 scope `stack` + `stack_ids()`**（2026-10-11 用户拍板）。族 ↔ scope 一一对应
   （`A`=ai-chain / `H`=http-contract / `S`=stack）；`stack` 不进任何豁免集，
   避免扩大漂移/幻觉分母、让门禁对本次改动失明。**票 02 第一件事**是扩
   `regression/divergences.py` 的正则与访问器。
9. **新增 divergence 条目必须同改两条硬编码等式断言**：
   `test_regression_divergences.py:21`（ai-chain）、`test_acceptance_024.py:155`（http-contract）。
10. **评测集在跑指标之前定稿**，不允许事后回溯调整真值（票 03）。
11. **取消分支的 span 缺口顺手修**：`protocol.py:66` 的 `except Exception` 捕不到
    `CancelledError`，补 `BaseException` 分支写 `cancelled` span（落点票 02「顺带修」）。
12. **本阶段不动简历**（含技能栏 `Docker 基础`）。

## Fog / 待观察

- **票 04 的方案选择**（端口内 vs 新 `RerankPort`）会牵动回放纪律，票内先做，结论回写本文件。
- **票 08 改 `SPEC.md:398` 措辞**会触碰「生成不可降级」这条写死原则，
  票内需同时改代码三处 docstring，避免文档与运行时不一致。
- **契约变更的连锁**：票 03 给 `MetricsReport` 加字段、票 05/06 加端点，
  两者都会让 `contracts/openapi.json` 重导；前者还要确认前端契约测试能否解析新字段。

## 自动执行约定（2026-10-11 用户授权，睡前进度自持）

用户授权：**自主跑完 01→09（含可选的 09）**；遇到选择一律取本文件与票面写明的推荐值；
需要业务数据时**可以自己往数据库加**（仅限数据库操作）；前端新增功能必须**美化到
与现有风格一致**（element-plus + 现有卡片/表格规范）；票 09 若炸就回滚那一票。

落点默认值（与 spec.md §7 一致，不再逐次追问）：

1. commit 前缀 `[TICKET-AC-NN]`；**不 push**，只落本地提交。
2. 票 04 重排放在 `RetrievalPort` 实现层内部（不新增 `RerankPort`）。
3. 票 05 越权访问已认领工单 → **404**。
4. 票 06 撤回用**软删**（保留审计痕迹），`source` 枚举校验非法值 422。
5. 票 07 不做患者开关；取过敏史 + 最近 3 条档案、合计 ≤600 字。
6. 票 03 标注集**先定稿再跑指标**，定稿后不允许回溯改真值。
7. 每票完成即登记 divergence、跑双端测试、做双轴 review、写 Comments、提交。
8. 若某票被权限/网络卡住：记进该票 Comments，**跳到下一张不阻塞的票**，
   最后回头补，不静默放弃。
9. 不碰 `FUNCTIONAL_SPEC.md`；不手改 `contracts/openapi.json`（一律重导）；
   `regression/ports.py` 保持零外部 import；不打印 `.env` 里的任何凭据。
