# 18: 健康档案

**What to build:** 医生为患者建立、修改、删除就诊档案，患者查看本人档案。归属校验在这里是硬要求：医生碰不到他人名下的档案，主诉的「标题：正文」编码约定两端一致。

**Blocked by:** 12（认证与个人中心）

**Status:** done
Completed: 05c934f

- [x] 医生可从患者选项列表建档、修改、删除；患者查看本人档案
- [x] 医生访问或改动他人名下档案返回 404，且数据不变
- [ ] 主诉按「标题：正文」编码（全角冒号）提交；医生端按第一个全角冒号拆回，无冒号时整串作为标题 —— **承接 TICKET-019**
- [x] 档案类型与备注字段的校验失败返回 422

## Comments

TICKET-016 挂账逐条结论（在本票处理）：

- **(a) 已修复，本票加固。** `/graph/infer` 在 TICKET-016 的复查提交 `683d169`
  已改为把 Skill span 经 `TraceRepository` 落库（与 `/chat` 同一条持久化路径），
  已有 `test_infer_persists_exactly_one_graph_inference_span` 断言。本票把断言推进
  到 B-4 的读回 seam（`TraceRepository.spans_for`），并补一条「图谱不可用（503）
  时仍恰好留下一条 span」的用例，锁死 AC-B-28。
- **(b) 本票修复。** `/traces` 的 `start` / `end` 查询参数此前由 FastAPI 声明为
  `format: date-time`（RFC3339 语义），与 SPEC.md 5.1 固定的
  `YYYY-MM-DD HH:mm:ss` 不符。选择：**去掉 `format`，改用与响应侧一致的
  `pattern`**。理由：SPEC 5.1 已把空格分隔格式定为线上唯一格式，声明必须描述实际
  发出的形状；既不复用 RFC3339，也不改回 ISO。新增 `core.serialization.DateTimeQuery`
  注解，契约由 `server/scripts/export_contract.py` 重新生成（未手改 openapi.json，
  `sse-events.json` 未动）；解析仍由 Pydantic 宽松处理。

验收清单逐条结论：

- 医生可从患者选项列表建档、修改、删除；患者查看本人档案 —— **已实现**。六端点见
  `SPEC.md` 5.4「预约与健康档案」，前端 `DoctorPatientsView` / `RecordsView`。
- 医生访问或改动他人名下档案返回 404，且数据不变 —— **已实现**。仓储层以「档案号
  **且** 医生号」过滤，越权更新/删除返回 404 且记录不变（测试逐条断言数据未变）。
- 主诉按「标题：正文」编码 —— **承接 TICKET-019**。`SPEC.md` 5.3 的
  `HealthRecordCreateRequest` 没有主诉字段（`FUNCTIONAL_SPEC.md` 4.3.6 的
  `t_health_record` 同样没有）；「主诉」是人工问诊 `t_doctor_consult.chief_complaint`
  的字段，其 `标题：正文`（全角冒号）编码约定见 `FUNCTIONAL_SPEC.md` 5.15 / SPEC
  AC-F-15，属 TICKET-019 的人工问诊闭环（本票边界明确不含 19–22）。
- 档案类型与备注字段的校验失败返回 422 —— **已实现**（就契约定义的字段而言）：
  `record_type` 必填 1..50、`diagnosis` ≤255，缺失/越界返回 422（测试覆盖）。
  健康档案契约中没有「备注」字段（备注是预约 `t_appointment.remark` 的字段，属
  TICKET-017，已落地）。

挂账（承接票）：

- 患者选项的「问诊人」一支要等 TICKET-019 的 `t_doctor_consult` 落地后并入
  `HealthRecordRepository.patient_options`；本票先覆盖「预约人 ∪ 已建档人」
  （`FUNCTIONAL_SPEC.md` 5.16 的前两支）。
