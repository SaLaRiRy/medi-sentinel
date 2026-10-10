# 03: 检索质量评测集 + recall@k / MRR（顺手修 replay 丢证据的缺陷）

**What to build:** 全仓**没有任何检索质量指标**（`recall@k` / `MRR` / `nDCG` 零命中）。本票新增：

1. `server/regression/retrieval_eval.py`：读标注集 → 跑 `RetrievalPort.search` →
   算 `recall@1` / `recall@5` / `MRR`。纯函数部分与端口调用部分分开，纯函数可离线单测。
2. `server/regression/cases/retrieval-v1.json`：**20–30 条** `query → 相关文档文件名` 标注
   （口径见 spec.md §7 第 3 条：**二值相关**，命中标注文件即相关，单 query 可标多文件）。
3. 一条命令可复现：`cd server; .venv\Scripts\python.exe scripts\regression.py retrieval-eval --set retrieval-v1`
   （子命令命名与现有 `record|replay` 一致）。
4. **顺手修一个真实缺陷**：`server/regression/replay.py:114-131` 计算了 `evidence_matched`，
   但 `run_regression` 在 `:138-146` **把它丢掉了**，永远进不了报告 →
   把「证据一致率」并进 `MetricsReport`（`server/regression/metrics.py`）并让
   `compare_reports` 输出其差值。

**Blocked by:** 01

**Status:** ready-for-agent

## 验收清单

- [ ] 20–30 条标注 query-文档对，`recall@5` / `MRR` **可复现**（一条命令；同基线两次运行同值）
- [ ] **标注集先定稿再跑指标**：真值一经确认即冻结，**不允许事后回溯调整**
      （否则指标失去意义）。定稿时间与版本写进 Comments；后续只有**新版本**
      `retrieval-v2.json` 才允许修订
- [ ] 标注口径写进 `.scratch/agentic-consult/spec.md`（本票完成时回写）
- [ ] 指标可观察：`GET /api/v1/regression/runs/{run_id}` 的 `MetricsReport` 多一个字段
      → **这是契约变更**：`SPEC.md` §5.3 的 `MetricsReport` 行必须同步，
      并重导 `contracts/openapi.json`（**不加端点**，故 §5.4 的 78 与 `SPEC_ERROR_BRANCHES` 不变）
- [ ] `evidence_matched` 不再被丢：新字段在报告里可观察，且有测试钉住
- [ ] 前端契约测试仍绿（确认能解析新增 schema 字段；若不能，同票修
      `client/tests/contract.test.js` 的解析断言）
- [ ] `MetricsReport` 四项既有指标定义**不变**（SPEC.md 3.8「指标不可自定义」）

## TDD 要点

- 纯函数：`recall@k` 与 `MRR` 的手算用例（空集、全命中、部分命中、并列）。
- 可复现：同一标注集 + 同一假端口 → 两次运行结果逐位相等（`AC-B-39` 的同精神）。
- 证据率：构造一真一假端口响应 → 报告里证据率为 0.5。

## 边界与坑

- 评测要跑**真实** `RetrievalPort`（活库 + 嵌入），但**单测**必须用假端口；
  真实跑法写进脚本 usage，结果贴 Comments。
- 标注集是**版本控制的数据**，与 `cases/`、`baselines/` 同级，不要塞进 pytest 夹具
  （`server/regression/schema.py:3-6` 的既有约定）。

## Comments
