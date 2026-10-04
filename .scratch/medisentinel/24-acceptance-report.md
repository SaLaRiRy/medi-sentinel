# TICKET-024 端到端验收报告

**日期**：2026-10-04
**范围**：`issues/24-end-to-end-acceptance.md` 验收清单；`SPEC.md` §3/§4/§5/§6（AC-* 全表）；
`intentional-divergences.md` 的 `http-contract` 子集（H-1…H-12）。
**方式**：跑既有套件 + 逐条核对；不新写业务功能。唯一新增是 §B/§C 两项数据级对照的收口测试
（`server/tests/test_acceptance_024.py`）。

**结论**：**通过**。未发现须修复的缺陷。仅记录一处既有的、`SPEC.md` 未列但不属缺陷的差异：
`openapi.json` 多出 `GET /api/v1/health`（§5.4 未列，TICKET-001 就存在，见 §3）。

---

## 0. 套件运行结果

| 套件 | 命令 | 结果 |
|---|---|---|
| 后端 | `cd server && .venv\Scripts\python.exe -m pytest -q --basetemp=.tmp\pytest024b` | **819 passed**（原 811 + 新增 8） |
| 前端 | `cd client && npm test` | **48 files / 276 passed** |

新增验收测试 `server/tests/test_acceptance_024.py` 把「§5.4 端点表 ⇄ `openapi.json` ⇄
错误分支表」的一致性写成可执行断言（此前无自动化护栏）。它是**验收断言**，不是新功能；
按 red→green 先落断言，再跑既有实现验证为绿。

---

## 1. Ticket 验收清单逐条核对

| # | 清单项 | 证据 | 结论 |
|---|---|---|---|
| 1 | 保留项逐条通过 | 见下方「保留项」映射表 | ✅ |
| 2 | 有意修复六项逐条通过 | 见下方「有意修复」映射表 | ✅ |
| 3 | `probability` 在契约与代码中均不存在 | `test_graph_inference_skill.py::test_probability_does_not_exist_in_runtime_code_or_contracts`；全仓 grep：`probability` 只出现在测试与 `SKILL.md` 的「禁止出现」断言里，`contracts/`、`server/{skills,api,repositories,models}` 均无 | ✅ |
| 4 | 契约测试覆盖每端点成功与全部错误码分支；错误码真实 HTTP 状态码且与 `code` 一致 | `test_declared_error_branches.py`（声明覆盖 + 外壳形状）、`test_error_contract.py`（422/409 真实码 + 同码 body）、`test_contract_seam.py`（生成契约 == 提交契约、422 == 外壳），加每端点的 401/403/404/409/422 集成用例（§1.2/§4 引用） | ✅ |
| 5 | 每一 SSE 帧满足事件 Schema；6 条协议不变量逐条通过 | 服务端 `test_contract_seam.py`、`test_orchestration_normal_path.py:213`、`test_safety_gate_short_circuit.py:135`、`test_degraded_branches.py:117` 用 `Draft202012Validator` 校验各路径帧；前端 `contract.test.js` 用 Ajv 校验全部 7 类帧；逐条不变量见 §1.3 | ✅ |
| 6 | 前端不引入后端连接串/数据库客户端；全部调用经唯一出口；每条契约有测试；401/403 分流正确 | `package.json` 依赖仅 `vue`；`architecture.test.js`（视图不 import transport、仅 `api/client.js` import transport）；`contract.test.js`（客户端实际打出的 67 个请求全部命中契约路径）；`guard.test.js`（401 清会话跳登录 / 403 仅提示） | ✅ |
| 7 | 前端表单校验失败以前端提示呈现；绕过前端校验的请求仍被后端 422 拒绝 | 前端 `auth-views.test.js` 等表单用例；后端每端点的 422 集成用例（如 `test_create_rejects_invalid_fields_with_422`）+ `test_error_contract.py::test_validation_failure_returns_422_in_the_envelope` | ✅ |
| 8 | AC-E-01 至 AC-E-09 逐条通过 | 见 §1.4 | ✅ |

### 1.1 保留项映射（AC-B-44）

| 保留项 | 验证方式 |
|---|---|
| 14 实体语义 | `test_migrations*.py`（各表结构与约束）；`models/` 与 `FUNCTIONAL_SPEC.md` 附录 A 对照 |
| 三角色模型与令牌语义 | `conftest.py` 每角色一行（同名跨三表）；`test_auth_api.py::test_the_same_username_resolves_to_the_table_the_role_names` |
| 全部状态值（预约 0–3、工单 0/1、向量化 0–3、通用 0/1） | `test_appointments_api.py::test_status_update_writes_an_undefined_value_verbatim`（无迁移校验，写请求值）；前端 `appointment-status/consult-status/account-status/knowledge-view` 映射测试 |
| 级联删除范围与顺序 | `test_users_api.py::test_delete_patient_cascades_in_order_and_spares_others`、`test_doctors_api.py::test_delete_doctor_cascades_and_spares_unassigned_consults`、`test_consults_api.py::test_admin_delete_removes_the_ticket_and_its_replies` |
| 科室删除保护 | `test_departments_api.py::test_delete_a_department_with_doctors_is_409_and_changes_nothing` |
| 档案归属校验 | `test_records_api.py::test_update_of_another_doctors_record_is_404_and_changes_nothing`、`::test_delete_of_another_doctors_record_is_404_and_keeps_it` |
| 主诉编码约定 | 前端 `complaint.test.js` / `consult-view.test.js`（AC-F-15「标题：正文」全角冒号）；后端原样存取（`test_consults_api.py`） |
| 会话标题与消息计数（前 20 字 + 省略号、+2、最近 6 条） | `test_chat_send_api.py::test_new_session_gets_its_title_from_the_first_20_characters`、`::test_short_message_is_used_as_the_title_without_an_ellipsis`、`::test_a_completed_turn_stores_both_messages_and_adds_two_to_the_count`、`::test_only_the_most_recent_six_prior_messages_reach_the_model`；`test_stream_lifecycle.py`（`message_count`） |
| 分页外壳、时间格式、角色展示映射 | `test_contract_seam.py::test_pagination_payload_has_the_declared_shape`；`test_contract_seam.py::test_the_contract_never_declares_rfc3339_date_time`；各列表端点分页用例 |

### 1.2 有意修复映射（AC-B-45）

| 修复 | 验证方式 |
|---|---|
| 症状词表统一 | `test_symptom_normalization_skill.py::test_the_vocabulary_is_the_only_symptom_and_alias_table`、`::test_chat_and_graph_chains_produce_the_same_standard_set` |
| `coverage` 更名 | `test_graph_inference_skill.py::test_candidates_are_ranked_by_match_count_with_explicit_coverage`、`test_graph_api.py::test_infer_ranks_by_coverage_and_never_exposes_probability` |
| 科室缺失为 `null` | `test_graph_inference_skill.py::test_missing_department_is_null_not_a_dash`；契约 `sse-events.json` / `openapi.json` 的 `DiseaseCandidate.department` 为 `["string","null"]` |
| 无无效参数 | `test_graph_adapter.py::test_neighbours_bind_depth_into_the_query_and_return_the_subgraph`、`::test_neighbours_reject_a_depth_outside_the_supported_range`（`depth` 真实生效 1..5） |
| 截断规则显式 | `test_graph_inference_skill.py::test_candidates_beyond_the_limit_are_truncated_not_silently`、`::test_trace_digest_records_the_truncation_rule`（`PROMPT_GRAPH_LIMIT=5`，前 10 回传 / 前 5 进提示词）；`SKILL.md` 声明 |
| 降级不阻断 | `test_degraded_branches.py`、`test_chat_send_degraded_api.py`（200 + `done.degraded`） |

### 1.3 SSE 6 条协议不变量逐条

| 不变量 | 验证方式 |
|---|---|
| 1. `session`、`trace` 为前两帧且顺序固定 | `test_stream_lifecycle.py`（`types[:2] == ["session","trace"]`）、`test_safety_gate_short_circuit.py` |
| 2. 拦截路径：`safety` 出现、`content` 0 次、`skills_run==["safety-gate"]`、`done.references/graph` 为空 | `test_safety_gate_short_circuit.py` |
| 3. 正常路径：`safety` 不出现、`done` 恰好 1 次 | `test_orchestration_normal_path.py` |
| 4. `done` 与 `error` 互斥且流以其一结束 | `test_stream_lifecycle.py::test_the_stream_ends_with_done_or_error_but_never_both` |
| 5. 任何帧 `trace_id` 与 `trace` 帧一致 | `test_safety_gate_short_circuit.py:80`、`test_orchestration_normal_path.py` |
| 6. 未知 `type` 被前端忽略而不中断 | `client.test.js::ignores a frame type the contract does not know, without stopping the stream` |

### 1.4 端到端场景 AC-E-01…09

| 场景 | 验证方式 | 结论 |
|---|---|---|
| AC-E-01 | `test_orchestration_normal_path.py::test_acceptance_scenario_headache_and_fever_runs_end_to_end`（归一化含 `头痛`/`发热`、候选疾病、`content` 非空、`done` 含引用与候选、5 Skill span + 1 LLM span） | ✅ |
| AC-E-02 | `test_safety_gate_short_circuit.py` | ✅ |
| AC-E-03 | `test_safety_gate_skill.py`（否定式不拦截） | ✅ |
| AC-E-04 | `test_chat_send_degraded_api.py`（图不可用仍 200，`done.degraded` 含 `graph`） | ✅ |
| AC-E-05 | `test_knowledge_api.py`（上传返回 `{id,file_name}`）、`test_knowledge_lifecycle.py::test_vectorize_moves_a_file_from_uploaded_to_indexed`（处理中 → 已向量化；`chunk_count == 向量条目数`） | ✅ |
| AC-E-06 | `test_records_api.py::test_delete_of_another_doctors_record_is_404_and_keeps_it` | ✅ |
| AC-E-07 | `test_departments_api.py::test_delete_a_department_with_doctors_is_409_and_changes_nothing` | ✅ |
| AC-E-08 | `test_users_api.py::test_delete_patient_cascades_in_order_and_spares_others` | ✅ |
| AC-E-09 | `test_regression_record_replay.py`（拦截率 100% / 误拦率 0% / 漂移率 0% / 可复现）、`test_regression_script.py::test_replay_of_the_committed_baseline_succeeds` | ✅ |

---

## 2. 必备对照 A：registry `http-contract` 子集（H-1…H-12）

方法：逐条打开登记册 → 定位端点/行为 → 读现行为源码 → 对照「legacy 出处」确认是**有意变更** →
以既有集成/契约测试作为验证。全部 12 条均确认「现行为 == 登记册记录的现行为」，且 legacy 行为
已被有意改变（非漏改、非误改）。

| 编号 | 端点 | 现行为（legacy → now） | 验证方式 | 结论 |
|---|---|---|---|---|
| H-1 | `POST /auth/register` | 重名 `400` → **`409 用户名已存在`** | 源码 `services/auth_service.py:62`；测试 `test_auth_api.py::test_register_rejects_a_taken_username_with_409` | ✅ 有意（`FUNCTIONAL_SPEC.md:222,1132`） |
| H-2 | 全端点契约可见性 | 端点从 `include_in_schema=False` → **发布进 `openapi.json`** | 全仓无 `include_in_schema`（grep 空）；`api/v1/__init__.py` 全量 `include_router`；`test_contract_seam.py::test_committed_openapi_matches_the_application`；`test_declared_error_branches.py` 按 §5.4 取 `paths[path][method]` | ✅ 有意（契约 seam 解冻，011/012/014） |
| H-3 | `DELETE /knowledge/{id}` | 不存在 **恒成功 → `404`** | 源码 `api/v1/knowledge.py:175`；测试 `test_knowledge_api.py`（`DELETE /knowledge/9999` → 404；revectorize `:155` 同理） | ✅ 有意（`FUNCTIONAL_SPEC.md:1273`） |
| H-4 | 内容端点 PUT/DELETE/公开详情 | 更新/删除**恒成功**、公告详情未发布返回 `data:null` → **PUT 404 + DELETE 404 + 公开详情 404** | 源码 `api/v1/articles.py:162,178,193`、`api/v1/notices.py:119,135,150`；测试 `test_articles_api.py` / `test_notices_api.py` 的 missing/unpublished 404 用例 | ✅ 有意（`FUNCTIONAL_SPEC.md:413,414,1272,1540`） |
| H-5 | `GET /stat/consult-trend`、`/stat/user-growth` | `days` **无上下界 → 限定 `1..365`，越界 `422`** | 源码 `api/v1/stat.py:121,150`（`ge=1, le=365`，常量 `services/stat_service.py:14-16`）；测试 `test_stat_api.py::test_trend_days_out_of_range_is_422` | ✅ 有意（`FUNCTIONAL_SPEC.md:1154`） |
| H-6 | `PUT /appointments/{id}/status`、`DELETE /appointments/admin/{id}` | 目标不存在**仍成功 → `404`** | 源码 `api/v1/appointments.py:185,201`（模块头 `:11` 自述）；测试 `test_appointments_api.py::test_status_update_of_a_missing_appointment_is_404`、`::test_delete_of_a_missing_appointment_is_404` | ✅ 有意（`SPEC.md §7.3`；`FUNCTIONAL_SPEC.md:381,1539`） |
| H-7 | `POST /consults/{id}/replies` | 任一医生可回复任意工单 → 已被其他医生认领时 **`409` 且不写入回复** | 源码 `api/v1/consults.py:161`、`repositories/doctor_consults.py:24,134`；测试 `test_consults_api.py::test_replying_to_another_doctors_ticket_is_409_and_writes_nothing` | ✅ 有意（`SPEC.md §7.2`；`FUNCTIONAL_SPEC.md:1244,1517`） |
| H-8 | `PUT/DELETE /records/doctor/{id}` | 不存在时 legacy 返 200 业务错 → **`404`** | 源码 `api/v1/records.py:170,188`；测试 `test_records_api.py::test_update_of_a_missing_record_is_404`、`::test_delete_of_a_missing_record_is_404`（含越权他人档案 404） | ✅ 有意（`FUNCTIONAL_SPEC.md:385,1259-1260`） |
| H-9 | `POST /consults/{id}/replies`、`DELETE /consults/admin/{id}` | 目标不存在 → **`404`** | 源码 `api/v1/consults.py:159,200`；测试 `test_consults_api.py::test_reply_to_a_missing_ticket_is_404`、`::test_delete_of_a_missing_ticket_is_404` | ✅ 有意（`FUNCTIONAL_SPEC.md:358-359`） |
| H-10 | `users` / `doctors` / `departments` PUT/DELETE；科室删除保护 | PUT/DELETE 不存在 → **`404`**；科室仍有关联医生删除 → **`409`** 且不落库 | 源码 `api/v1/users.py:175,194,210`、`api/v1/doctors.py:210,230,246`、`api/v1/departments.py:136,158,160`；测试 `test_users_api.py`/`test_doctors_api.py`/`test_departments_api.py` 的 missing 404 与 `test_delete_a_department_with_doctors_is_409_and_changes_nothing` | ✅ 有意（`FUNCTIONAL_SPEC.md:1220-1225`） |
| H-11 | 全部端点失败响应形状 | legacy「HTTP 200 + `body.code=400`」→ **真实 HTTP 状态码 + 同码 `code`**（H-1…H-10 的共享上层） | 源码 `core/errors.py:10-27`（`ApiError` / 统一处理器以 `status_code` 同时设 HTTP 与 body）、`core/response.py`；测试 `test_error_contract.py::test_validation_failure_returns_422_in_the_envelope`、`::test_business_error_carries_its_real_status_and_message`、`test_declared_error_branches.py::test_declared_error_branches_carry_the_envelope` | ✅ 有意（`SPEC.md §3.6/§5.1`、AC-B-43；legacy 设计错误，非应保留行为） |
| H-12 | `PUT /users/{id}/status` | 请求形态 **query 参数 → JSON body `{status:int}`** | 源码 `api/v1/users.py:61-62`（路由 + `UserStatusRequest`）；契约 `openapi.json` 该操作仅路径参 `user_id`、`requestBody=UserStatusRequest{status:int}`；测试 `test_users_api.py::test_update_status`（json body）与 `::test_update_status_of_a_missing_patient_is_404` | ✅ 有意（`FUNCTIONAL_SPEC.md:336` 明确「走查询参数」） |

> 应用顺序照登记册：先接受 H-11「失败不再走 200」，再逐端点接受 H-1…H-10 的 `404`/`409`。
> 新增测试 `test_acceptance_024.py::test_024_consumes_the_http_contract_divergence_subset` 固定
> 「024 消费的正是 H-1…H-12」这一交接点。

---

## 3. 必备对照 B：`SPEC.md` §5.4 端点表 ⇄ `contracts/openapi.json`

方法：解析 §5.4 全部 8 张表（方法 + 路径），按 `{参数}` 归一化后与 `openapi.json` 的
`paths` 全量比对（`server/tests/test_acceptance_024.py`）。

| 检查 | 结果 |
|---|---|
| §5.4 列出的端点是否全部在 `openapi.json` | **是，78/78**，无缺失 |
| 新增 `/regression/*` 三端点是否在 | **是**：`POST /regression/runs`、`GET /regression/runs/{run_id}`、`GET /regression/baselines` |
| `openapi.json` 是否多出 §5.4 未列的端点 | 仅 1 个：`GET /api/v1/health`。`SPEC.md` §5.4 未列它，属 TICKET-001 骨架的既有端点，`test_declared_error_branches.py` 注释已声明「`/health` 除外，5.4 未列」。**记录，不作为差异修复** |

> 结论：§5.4 与 `openapi.json` **双向对齐**（差异仅为已声明的 `/health`）。契约由
> `scripts/export_contract.py` 生成并提交，`test_contract_seam.py` 断言「生成 == 提交」。

---

## 4. 必备对照 C：AC-B-41 错误码分支完整性

方法：把 `test_declared_error_branches.py::SPEC_ERROR_BRANCHES` 与 §5.4 的「错误码」列
逐端点比对，并独立地与 `openapi.json` 的实际声明比对（不依赖该表自证）。

| 检查 | 结果 |
|---|---|
| `SPEC_ERROR_BRANCHES` 是否覆盖 §5.4 全部端点 | **是，78/78**，键集与 §5.4 完全一致（无遗漏、无多余） |
| 表中是否漏掉某端点的 §5.4 错误码 | **否**，逐端点 `§5.4 码 ⊆ 表中码`（本例相等） |
| `openapi.json` 是否有端点漏声明 §5.4 错误分支 | **否**，逐端点 `§5.4 码 ⊆ 已声明码`；且每端点均声明 `200` |
| 声明的非 2xx 分支是否为统一外壳 | **是**，`test_declared_error_branches_carry_the_envelope` 断言均为 `Envelope_NoneType_` 且媒体类型 `application/json; charset=utf-8` |
| 是否用真实 HTTP 状态码且与 body `code` 一致 | **是**，`test_error_contract.py` + `test_contract_seam.py::test_the_declared_validation_error_branch_is_the_envelope`；AC-B-43 |

> 结论：AC-B-41 在**声明层**（§5.4 ⇄ 表 ⇄ 契约）与**运行层**（每端点 404/409/422 集成用例 +
> 真实码 == body `code`）均完整，无端点漏声明错误分支。

---

## 5. 记录的问题 / 边界说明

1. **`GET /api/v1/health` 不在 §5.4**（§3）：既有事实，非本票引入、非缺陷；登记在案。
2. **`P95 延迟取录制值**（TICKET-023 设计取舍）：`test_regression_record_replay.py` 说明回放
   P95 取基线录制 `duration_ms`，是为满足 AC-B-39「两次回放指标完全一致」；延迟漂移改由
   `v1` vs `v2` 录制值对比观察。已在 023 的 Design 记录，非缺陷。
3. 无端点漏声明错误分支、无 H-* 误判为回归、无未标识的行为漂移。**未发现问题需新票修复。**

---

## 6. `/tdd` 与 `/code-review` 说明

- **`/tdd`**：验收以「跑既有套件 + 逐条核对」为主；仅 §B/§C 两项此前无自动化护栏，按 red→green
  补 `test_acceptance_024.py`（断言取自 `SPEC.md` 这一独立事实源，非重算实现）。
- **`/code-review`**：子代理通道本环境投递失败，按约定由本代理跑**两遍独立评审**
  （Standards 轴 + Spec 轴），分开报告、不合并；结论见 `issues/24-*.md` 的 Comments。
