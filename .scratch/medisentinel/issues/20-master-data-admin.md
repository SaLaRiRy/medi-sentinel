# 20: 医患与科室主数据

**What to build:** 管理员对患者、医生、科室的完整维护，含删除患者时的级联清理顺序，以及「科室下还有医生就不许删」的保护。这是其余业务域依赖的主数据。

**Blocked by:** 12（认证与个人中心）

**Status:** done
Completed: 7775b76

- [x] 患者与医生的增删改查、状态切换可用；用户名重复返回 409
- [x] 删除患者按既定顺序级联清理其会话与消息、工单与回复、预约、档案
- [x] 科室增删改查可用；删除仍有关联医生的科室返回 409，且科室未被删除
- [x] 公开的医生列表与科室列表无需认证即可访问
- [x] 账号状态 0/1 语义与展示映射正确，未知值回退到既定默认

## Comments

落地内容（`SPEC.md` 5.4「患者与医生主数据」）：

- 后端：新增迁移 `0010` 与 `t_department`，并在 `api/v1/{users,doctors,departments}.py`
  落地 16 个端点（患者 5、医生 6、科室 5）。公开目录 `GET /doctors`（状态 1 且已分配
  科室，可按科室/关键字过滤）与 `GET /departments`（状态 1，`sort_order` 升序、同值按
  编号倒序）无需认证；其余增删改停均限 `admin`。
- 级联清理：`repositories/cascade.py` 按 `FUNCTIONAL_SPEC` 5.11 的顺序实现删除患者
  （消息 → 会话 → 回复 → 工单 → 预约 → 档案 → 患者）与删除医生（回复 → 工单 → 预约 →
  档案 → 医生）；**未指派的工单保持「待分配」不动**（AC-E-08）。
- 科室保护：删除仍有关联医生的科室返回 409 且不落库；`doctor_count` 只统计状态 1 的
  医生，删除保护统计**全部**关联医生（5.12 / 5.13 / AC-E-07）。
- 前端：新增患者/医生/科室三个管理视图与账号状态映射
  （`client/src/account/status.js`），路由 `/admin/{users,doctors,departments}`；患者预约
  表单的医生/科室改用公开主数据目录下拉填充。`contracts/openapi.json` 由
  `scripts/export_contract.py` 重新生成，未手改；`sse-events.json` 未动。

承接的挂账（逐条结论）：

- **TICKET-019 移交第 1 条（级联清理）**：本票落地。删除患者/医生时对
  `t_doctor_consult` / `t_doctor_reply` 的清理已按 5.11 顺序实现并有测试覆盖；未指派
  工单不在删除范围内。
- **TICKET-017 挂账（预约下拉）**：需要回接，已作为本票范围内的必要扩展落地——患者端
  预约的医生/科室改为从公开主数据目录（`GET /doctors`、`GET /departments`）下拉选择；
  提交体仍是编号，017 行为不变。若不回接，本票新建的主数据对患者仍不可达，挂账无法
  真正结清。
- **AC-B-41 收口**：新端点自带 `responses=error_responses(...)`；同时把 TICKET-019 未
  纳入的 TICKET-016 图谱端点与 TICKET-018 档案端点补进
  `tests/test_declared_error_branches.py`，5.4 端点全覆盖（`/health` 除外，5.4 未列）。

一处刻意的契约取舍：`POST/PUT /users`、`POST/PUT /doctors` 在口令与确认口令不一致
（或缺确认口令）时返回 400 —— 依 `SPEC.md` 5.2 / `FUNCTIONAL_SPEC` 5.9，「两次口令
不一致」属 400；5.4 的逐端点错误列表未列 400，故这些路由在 5.4 之外**多声明** 400，
AC-B-41 的「不得漏声明」断言据此仍然成立。
