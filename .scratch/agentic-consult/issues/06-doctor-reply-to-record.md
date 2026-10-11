# 06: 闭环 B —— 医生回复 → 档案沉淀（AI 建议不得直接进病历）

**What to build:** `server/models/health_record.py:29-42` 的 `t_health_record` 只有
`user_id` / `doctor_id` / `record_type` / `diagnosis` / `treatment` / `prescription` / `visit_date`，
**没有来源标注、没有 `consult_id`**；医生回复工单不会生成档案，闭环断在第二段。

1. 迁移 `server/migrations/versions/0013_record_source_link.py`：`t_health_record` 加
   - `source`（枚举 `ai` / `doctor` / `patient`，默认 `doctor`，索引）
   - `consult_id`（可空，关联 `t_doctor_consult`，索引）
   - `withdrawn`（0/1 软删，配合「可撤回」；若前端不用软删就换成等价状态字段）
2. **AI 建议不得直接变成病历**：`source='ai'` 的档案**只能由医生的显式确认动作产生**
   （确认者 = 档案的 `doctor_id`），且**可撤回**（撤回后不出现在患者档案列表）。
3. 端点（走 §3.1 六处同步）：
   - `POST /records/doctor/from-consult`：由工单 id + 医生确认内容生成档案（`doctor`）
   - `POST /records/doctor/{record_id}/withdraw`（若采用软删）
4. 前端：医生回复工单后出现「沉淀为档案」确认动作；患者档案列表显示来源。

**Blocked by:** 05（需要工单 ↔ 会话/患者关联）

**Status:** done
Completed: e80e8e8

## 验收清单

- [ ] 迁移可升可降；`source` 有取值校验（非法值 422）；`consult_id` 可空 + 索引
- [ ] `source='ai'` 的档案**必须**带医生确认证据（`doctor_id` 非空 + 动作端点产生），
      并有测试证明「AI 建议不会未经确认直接入库」
- [ ] 撤回语义：撤回后 `GET /records/my` 不返回该档案；不可撤回他人的档案
- [ ] 既有 `GET/POST/PUT/DELETE /records/doctor*` 行为不回归
      （`server/tests/test_records_api.py` 全绿）
- [ ] 六处同步全绿（同票 05 的清单口径）
- [ ] divergence 登记（scope `http-contract`）
- [ ] 新条目编号 `H-14`，**同票**同步两处硬编码等式断言：
      `server/tests/test_acceptance_024.py:155` 与
      `server/tests/test_regression_divergences.py:22` 的
      `http_contract_ids(...) == [H-1…H-12]` 一并改成 `range(1, 15)`
- [ ] 双端测试通过

## TDD 要点

- 未确认路径：只有工单回复、没有确认动作 → 档案表零新增。
- 确认路径：同一工单重复确认 → 幂等（不产生第二条档案，或按票内规则明确允许但带来源）。
- 撤回：撤回后再确认 → 重新可见。
- 越权：医生 A 撤回医生 B 的档案 → 404。

## 边界与坑

- 「可撤回」若用硬删，会丢掉审计痕迹 → 优先软删；两者取舍写进票内结论。
- 档案文本可能来自 AI 生成内容 → 落库前确认**没有**把整段模型输出写进 trace
  （`SPEC.md` 3.7，summary 只存长度类事实）。
- `t_health_record.record_type` 的库层可空 vs 请求层必填（`models/health_record.py:8-10` 已注明）
  ——新端点沿用请求层必填。

## Comments

**完成（2026-10-11）。** 闭环第二段打通：医生把工单结论**确认**为档案，且可撤回。

### 交付

**后端**

- 迁移 `0013_record_source_and_withdraw.py`：`t_health_record` 加
  `source`（`String(10)`，默认 `doctor`，索引）/ `consult_id`（可空，索引）/
  `withdrawn`（0/1 软删）。活库已 `alembic upgrade head` → `0013 (head)`。
- `models/health_record.py`：三列 + `RECORD_SOURCES` 常量。
- `repositories/health_records.py`：`create(source=, consult_id=)`、
  `find_by_consult`（幂等键）、`withdraw`（软删）、两个列表查询都过滤 `withdrawn == 0`。
- `api/v1/records.py`：
  - `HealthRecordView` 加 `source` / `consult_id`（患者能看到来源）；
  - `POST /records/doctor/from-consult`：要求工单**已被当前医生认领**（否则 404）；
    同一工单重复确认返回已有那条（**幂等**，不产生第二条档案）；
  - `POST /records/doctor/{id}/withdraw`：软删；他人档案 404。

**AI 建议不得直接进病历**：`source='ai'` 只有 `from-consult` 这一个写入口，
且必须携带医生身份；`source="patient"` 由请求 Schema 直接 422 拒绝。
撤回走软删——`FUNCTIONAL_SPEC.md` 5.11 的硬删会把审计痕迹一起丢掉。

**前端**（element-plus，沿用现有卡片/表格/标签风格）

- F-1 出口 `createRecordFromConsult` / `withdrawRecord`；契约计数 68 → 70。
- 医生端 AI 上下文弹窗内新增「沉淀为档案」表单（档案类型 / 诊断 / 处理 + 来源选择）：
  空表单给必填提示、成功后显示「已沉淀为档案 #id（来自 AI 建议）」。
- 患者端档案表新增「来源」列：`来自 AI 建议` 用 warning 标签，`医生结论` 用 info 标签。

### 连带面（同票全部同步）

- `SPEC.md` §5.3/§5.4：新增 `RecordFromConsultRequest` 与两个端点行，
  `len(SPEC_5_4)` 79 → **81**；`contracts/openapi.json` 重导
- `test_declared_error_branches.py` 新增两键；`client/tests/contract.test.js` 68 → **70**
- `H-14` 登记（scope `http-contract`）；`test_acceptance_024.py:155` 与
  `test_regression_divergences.py:22` 的 `range(1, 14)` → `range(1, 15)`
- 迁移 head 断言 `0012` → `0013`（`test_migrations.py` × 2 与六个 `test_migrations_*.py`）

### TDD

`server/tests/test_record_from_consult.py` **14 项**：沉淀与来源 3 / 归属与越权 5 /
Schema 拒绝 1 / 撤回与可见性 4 / 未知档案 1。
前端 `doctor-consults-view.test.js` +1（空表单不落库 → 填好后带着 `source='ai'` 落库）。

### 套件

- 后端 `pytest -q --basetemp=.tmp\pytest-user` → **925 passed**
- 前端 `npm test` → **56 files / 327 passed**

### divergence

`H-14`（scope `http-contract`）已登记。
