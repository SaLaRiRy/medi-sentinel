# 05: 闭环 A —— 工单关联 AI 会话 + 医生查看 AI 上下文

**What to build:** `server/models/doctor_consult.py:29-37` 的 `t_doctor_consult` 只有
`user_id` / `doctor_id` / `chief_complaint` / `status`，与 AI 会话**零关联**——患者转人工后，
医生看不到 AI 已经问出来的候选疾病与引用，患者要重打一遍主诉。本票打通第一段：

1. 迁移 `server/migrations/versions/0012_consult_session_link.py`：给 `t_doctor_consult`
   加**可空** `session_id`（`Integer`，`index=True`），历史工单为 NULL。
   （迁移号接现有 `0011`，见 `docs/adr/0001`、`0002` 的命名约定。）
2. 患者端「转人工」带上会话：`ConsultCreateRequest` 加 `session_id: int | None`
   （同步 `SPEC.md` §5.3 的该行）。
3. **新端点** `GET /consults/{consult_id}/ai-context`（`doctor`）→ 返回该工单关联会话的
   AI 上下文：候选疾病、引用、原始主诉。
4. 前端：医生端工单详情展示 AI 上下文。

**Blocked by:** 无（与 01–04 独立）

**Status:** ready-for-agent

## 已拍板的决策：新端点做归属校验

现有 `GET /chat/sessions/{id}/messages` **故意不校验归属**（`server/api/v1/chat.py:224-232`；
`SPEC.md` §7.2「原样保留」；`intentional-divergences.md` 已登记为「**非**偏离」）。
新端点**不能照抄**这个行为。**理由已由用户拍板（2026-10-11）**：

- 患者读的是**自己的**会话 → 无越权面，历史行为保留；
- 医生读的是**被指派 / 待认领工单**的会话 → **工单本身就是授权凭证**；
  未认领工单对全体医生可见（`FUNCTIONAL_SPEC.md` 5.14），已认领工单只对负责医生可见；
  否则任何医生都能凭工单号遍历全部患者的 AI 对话。

## 必须走 §3.1 的「六处同步」（spec.md 4.1）

1. `server/api/v1/consults.py` 新路由 + `server/api/v1/__init__.py`
2. `SPEC.md` §5.4「人工问诊」表新增一行 →
   `server/tests/test_acceptance_024.py:94-96` 的 `len(SPEC_5_4) == 78` 改成 **79**
3. `server/tests/test_declared_error_branches.py` 的 `SPEC_ERROR_BRANCHES` 新增键
   （key 为**小写 method**）
4. `cd server; .venv\Scripts\python.exe scripts\export_contract.py` 重导
   `contracts/openapi.json`（**永不手改**）
5. `client/tests/contract.test.js:177` 的 `expect(requested).toHaveLength(67)` → **68**
6. `client/src/api/client.js` 新增出口方法

## 验收清单

- [ ] 迁移可升可降（`test_migrations_consults.py` 同类测试补一条）
- [ ] `t_doctor_consult.session_id` 可空 + 有索引；历史工单不受影响
- [ ] 转人工带上 `session_id` 后，工单可反查会话
- [ ] 越权路径有断言：非负责医生访问已认领工单 → 票内拍定状态码
      （建议 404，与 `/records/doctor/{id}` 的「不匹配即 404」一致），并写进 §5.4 与错误分支表
- [ ] 六处同步全绿：`test_acceptance_024.py`、`test_declared_error_branches.py`、
      `test_contract_seam.py`、`client/tests/contract.test.js`
- [ ] 双端测试：后端 `pytest -q --basetemp=.tmp\pytest`、前端 `npm test`
- [ ] divergence 登记（scope `http-contract`）
- [ ] 新条目编号 `H-13`，**同票**同步两处硬编码等式断言：
      `server/tests/test_acceptance_024.py:155` 与
      `server/tests/test_regression_divergences.py:22` 的
      `http_contract_ids(...) == [H-1…H-12]` 一并改成 `range(1, 14)`
- [ ] 若新端点关联的表有患者数据，确认 trace/日志**不落患者原文**（`SPEC.md` 3.7）

## TDD 要点

- 先写 API 测试：带 token 的医生拿到 AI 上下文；未认领工单的医生也能拿到；
  已认领给别的医生 → 404；患者角色 → 403；无 token → 401。
- 契约测试：新端点在 `openapi.json` 与 §5.4 里同时存在（`test_acceptance_024.py` 自动覆盖）。
- 迁移测试：`alembic upgrade` 后列存在、`downgrade` 后消失（沿用 `test_migrations_consults.py` 手法）。

## 边界与坑

- 历史工单 `session_id` 为 NULL → 端点要返回明确的空上下文（不是 500）。
- 会话可能已被删除：返回空上下文而不是 404（工单仍有效）。
- 工单与会话的归属不一致（工单 patient A、会话 patient B）要拒绝——**越权面在数据层也要挡**。

## Comments
