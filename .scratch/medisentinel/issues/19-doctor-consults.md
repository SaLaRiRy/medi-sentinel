# 19: 人工问诊工单

**What to build:** 患者向真人医生发起咨询：可指定医生，也可留空成为待分配工单；医生看到待分配工单并认领回复，先到先得；管理员分页查看并管理。

**Blocked by:** 12（认证与个人中心）

**Status:** done
Completed: d74197f

- [x] 患者提交工单，可指定医生或留空成为待分配
- [x] 医生看到待分配工单并可认领，先到先得
- [x] 回复已被其他医生认领的工单返回 409，且不写入回复
- [x] 管理员分页查看工单并可按状态过滤、删除
- [x] 工单状态 0/1 语义与展示映射正确

## Comments

落地内容（`SPEC.md` 5.4「人工问诊」）：

- 后端：`t_doctor_consult` / `t_doctor_reply`（迁移 `0009`）与六个端点
  `POST /consults`、`GET /consults/my`、`GET /consults/pending`、
  `POST /consults/{id}/replies`、`GET /consults/admin`、`DELETE /consults/admin/{id}`。
  抢单语义：工单无医生时首位回复者被写入为负责医生、状态无条件置 1；已被其他
  医生认领返回 409 且不写入回复。
- 前端：患者提交/查看、医生抢单回复、管理员分页过滤与删除；主诉按
  「标题：正文」（全角冒号）编码与拆解（AC-F-15），工单状态 0/1 展示映射（AC-F-11）。

承接的挂账（逐条结论）：

- **TICKET-018 挂账第 1 条（问诊人）**：已并入
  `HealthRecordRepository.patient_options` —— 可选患者 = 预约人 ∪ 问诊人 ∪ 已建档人，
  工单 `doctor_id` 为当前医生时提交人计入，「待分配」工单不归属任何医生。
- **TICKET-018 挂账第 2 条（主诉）**：`t_doctor_consult.chief_complaint` 落地，
  后端原样存取，编码/拆解在前端（`SPEC.md` 5.15 / AC-F-15）。
- **已拍板：`/chat/admin/sessions`**：按 `SPEC.md` 5.4 以 `admin` 角色实现分页查看
  全部会话（工单描述里的「医生」不参与，与 SPEC 与现状一致）。
- **AC-B-41 旧端点错误分支**：本票统一补 `responses=error_responses(...)`，
  覆盖 007–015 与 017 的预约端点；`contracts/openapi.json` 由
  `scripts/export_contract.py` 重新生成，未手改；`sse-events.json` 未动。

移交：删除患者/医生时对 `t_doctor_consult` / `t_doctor_reply` 的级联清理属
TICKET-020（其清单已含「工单与回复」），本票不动账号级联（`FUNCTIONAL_SPEC` 5.11）。
