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

**完成（2026-10-11）。** 检索第一次有了可复现的质量指标，回放自检也从「算了就丢」变成进报告。

### 交付

| 文件 | 变更 |
|---|---|
| `server/regression/retrieval_eval.py`（新增） | `recall_at` / `reciprocal_rank` 纯函数、`evaluate_retrieval` 端口评测、`load_case_set` |
| `server/regression/cases/retrieval-v1.json`（新增） | **30 条**标注 query-文档对，`frozen_at: 2026-10-11` |
| `server/scripts/regression.py` | 新子命令 `retrieval-eval --set retrieval-v1` |
| `server/regression/metrics.py` | `CaseOutcome.evidence_matched`、`MetricsReport.evidence_match_rate`、`compare_reports` 加差值 |
| `server/regression/replay.py` | 把 `evidence_matched` 真正接进 `CaseOutcome`（此前算完就丢） |
| `SPEC.md` §3.8 / §5.3 | 说明 `evidence_match_rate` 是**回放自检**，不是第五项指标 |
| `contracts/openapi.json` | 重导（永不手改） |

### 标注口径（先定稿再跑指标）

- **二值相关**：命中 `relevant` 里任一文件名即算相关；一条 query 可标多篇（q13 标了 2 篇）。
- **30 条**，覆盖全部 17 篇种子文档。先写标签、再跑指标，`frozen_at` 写死在文件里；
  冻结后不得回溯修改，口径变更只能出 `retrieval-v2`。
- 完整性有测试兜底：条数落在 20–30、id 唯一、**每条标注都指向真实存在的种子文档**。

### 实测结果

```
cd server; .venv\Scripts\python.exe scripts\regression.py retrieval-eval --set retrieval-v1

{"case_set_version": "retrieval-v1", "case_count": 30,
 "recall_at_1": 0.9833333333333333, "recall_at_5": 0.9833333333333333,
 "mrr": 1.0, "top_k": 5}
```

- **MRR = 1.0**：每条有命中的用例，第一篇相关文档都在第 1 位。
- **recall@1 = recall@5 = 29.5/30**：唯一缺口是多标签的 q13
  （「过敏性鼻炎和感冒有什么区别」标了 2 篇），只召回了其中 1 篇。
  按冻结纪律**不回溯改标签**。
- 观察（留给票 04）：检索是**分块级**的，5 个名额可能被同一个文件的多块占满，
  这是 q13 丢掉第二篇的原因之一；重排若按文档去重会顺带改善。

### TDD

`server/tests/test_retrieval_eval.py` 11 项：纯函数 4 / 端口评测 3 / 标注集完整性 3 / 参数校验 1。
另更新 `test_regression_metrics.py` 的「字段名冻结」断言（加 `evidence_match_rate`）——
这正是那类「加字段会撑破的硬编码断言」，必须同票改。

### 套件

- 后端 `pytest -q --basetemp=.tmp\pytest-user` → **883 passed**（873 + 10 新增，229 s）
- 前端 `npm test` → **56 files / 322 passed**（契约加了字段后仍能解析）

### 环境（与票无关，但会影响下一个人）

`server\.tmp\pytest` 的属主是沙箱账号 `CodexSandboxOffline`，当前账号（87590，非管理员）
**既列不出也删不掉**：`--basetemp=.tmp\pytest` 直接 `PermissionError`，
从仓库根递归搜索会报 2 个错误。本票改用 `.tmp\pytest-user`。
**需要用户用有权限的账号删掉 `server\.tmp\pytest`**（交接文档开头的同一件事又出现了）。

### divergence

无新条目：本票只加指标与报告字段，`S-1` 已在票 02 登记。
