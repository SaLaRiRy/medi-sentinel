# Intentional divergences registry（有意偏离登记册）

**用途**：TICKET-023（回归基线框架）与 TICKET-024（端到端验收与功能对等回归）
**共同引用的唯一事实源**。本册登记「新实现有意偏离 `FUNCTIONAL_SPEC.md` 现状行为」
的每一处。录基线 / 回放对比 / 功能对等回归之前必须先读本册，否则会把有意变更
误判为回归。

**证据约定**：每条同时给出 legacy 出处（`FUNCTIONAL_SPEC.md` 行号）与现行为出处
（`server/…:行号`），均经 grep 核对，不凭记忆。

## scope 标签（二选一或 both）

| 标签 | 消费方 | 含义 |
|---|---|---|
| `ai-chain` | TICKET-023 的 B-1 自动重放对比 | 影响一次问诊的输入集 → 各 Skill 输出 → 最终结果 → 耗时，会被回放对比消费 |
| `http-contract` | TICKET-024 的功能对等回归 | 影响 HTTP 端点的行为或契约形状（状态码、存在性、请求/响应形状） |

## 消费规则（023 / 024）

- **023**：对比逻辑**显式豁免 `ai-chain` 子集**（A-*），这些差异不作为回归失败判定；
  `http-contract` 子集（H-*）在 023 里**只记录不消费**，留给 024。换言之以「只读的
  登记表」形式嵌入 023，避免 023 的漂移率 / 幻觉率分母把有意变更算进去。
- **024**：`http-contract` 子集（H-*）逐条作为功能对等回归的「已变更」断言依据。
- 新增有意变更时，在此追加一行并标注 scope；本册是版本控制对象，随基线一同流转。

---

## ai-chain 子集（023 豁免）

| ID | 票号 | 行为描述 | legacy 出处 | 现行为出处 | scope |
|---|---|---|---|---|---|
| A-1 | 004 | 归一化输出顺序：**词表序 → 首次出现序**（按各表面词在文本中的首次出现位置排序、按标准症状去重） | `FUNCTIONAL_SPEC.md:253,523,985,1474,1533` | `server/skills/symptom_normalization/vocabulary.py:95,99-108` | ai-chain |
| A-2 | §3.6-1 | 症状词表统一：30 词提取表 + 22 条别名表（交集仅 `发烧`）→ **唯一一份**词表，对话链路与推理链路同等生效 | `FUNCTIONAL_SPEC.md:523,985,1533` | `server/skills/symptom_normalization/vocabulary.py:44-78` | ai-chain |
| A-3 | §3.6-2 | 字段更名：`probability` → **`coverage`**（语义仍为「命中数 ÷ 输入症状总数」，保留 2 位小数） | `FUNCTIONAL_SPEC.md:298,561,1013,1019,1476,1493` | `server/skills/graph_inference/inference.py:27,32` | ai-chain |
| A-4 | §3.6-3 | 科室缺失取值：字符串 `"-"` → **`null`**（展示层 `-` 由前端负责） | `FUNCTIONAL_SPEC.md:562,1016` | `server/skills/graph_inference/inference.py:20,53-59` | ai-chain |
| A-5 | §3.6-4 | 子图 `depth` 参数：存在但无效（实际只返回一跳）→ **真实生效**（1..`MAX_DEPTH`=5） | `FUNCTIONAL_SPEC.md:1534` | `server/api/v1/graph.py:124`；`server/graph/neo4j_adapter.py:29,91-98` | ai-chain |
| A-6 | §3.6-5 | 图谱结果截断：静默截为 5 条 → **规则显式化**（前 10 条回传 `done`、前 5 条进提示词，`PROMPT_GRAPH_LIMIT=5`，随 trace/`SKILL.md` 声明） | `FUNCTIONAL_SPEC.md:1021,1535` | `server/skills/graph_inference/inference.py:14-15,83`；`server/skills/orchestration/prompt.py:10-11,36` | ai-chain |
| A-7 | §3.6-6 | 外部依赖不可用：检索 / 图谱不可用即**整体失败** → **降级不阻断**（失败支路记 `degraded`，问答继续，`done.degraded` 标注） | `FUNCTIONAL_SPEC.md:1366-1367` | `server/skills/orchestration/skill.py:263-272,326` | ai-chain |

## http-contract 子集（023 只记录，024 消费）

| ID | 票号 | 行为描述 | legacy 出处 | 现行为出处 | scope |
|---|---|---|---|---|---|
| H-1 | 012 | 注册重名：`400` → **`409 用户名已存在`** | `FUNCTIONAL_SPEC.md:222,1132` | `server/services/auth_service.py:62`；`server/api/v1/auth.py:69` | http-contract |
| H-2 | 011/012/014 | 契约解冻：端点从 `include_in_schema=False`（隐藏）→ **发布进 `openapi.json`** | 契约 seam（非 `FUNCTIONAL_SPEC` 行为）；提交 `32de629`(011)、`5eec16f`(012)、`7c9e862`(014) | 全仓已无 `include_in_schema`；`server/api/v1/__init__.py` 全量 `include_router`；`contracts/openapi.json` | http-contract |
| H-3 | 015 | `DELETE /knowledge/{id}` 不存在：**恒返回成功** → `404` | `FUNCTIONAL_SPEC.md:1273` | `server/api/v1/knowledge.py:175` | http-contract |
| H-4 | 021 | 内容端点：**PUT 404 + DELETE 404 + 公开详情 404**（legacy 更新/删除恒成功；公告详情未发布返回 `data:null`） | `FUNCTIONAL_SPEC.md:413,414,1272,1540` | `server/api/v1/articles.py:162,178,193`；`server/api/v1/notices.py:119,135,150` | http-contract |
| H-5 | 022 | 统计 `days` 参数：**无上下界** → 限定 **1..365**，越界 `422` | `FUNCTIONAL_SPEC.md:1154` | `server/api/v1/stat.py:121,150` | http-contract |
| H-6 | 017 | 预约状态/删除不存在：**仍返回成功** → `404`（`SPEC.md` §7.3 点名「本规格已将其改为 404，属契约收紧」） | `FUNCTIONAL_SPEC.md:381,1539` | `server/api/v1/appointments.py:185,201`（模块头 `:11` 自述） | http-contract |
| H-7 | 019 | 抢单冲突：任一医生可回复任意工单 → 已被其他医生认领时 **`409`** 且不写入回复（`SPEC.md` §7.2 纳入范围） | `FUNCTIONAL_SPEC.md:1244,1517` | `server/api/v1/consults.py:161`；`server/repositories/doctor_consults.py:24,134` | http-contract |
| H-8 | 018 | `records/doctor` PUT/DELETE 不存在：legacy 返回「档案不存在或无权限」（HTTP 200 业务错）→ **`404`** | `FUNCTIONAL_SPEC.md:385,1259-1260` | `server/api/v1/records.py:170,188` | http-contract |
| H-9 | 019 | consults 回复不存在 → `404`；admin 删除不存在 → `404` | `FUNCTIONAL_SPEC.md:358-359` | `server/api/v1/consults.py:159,200` | http-contract |
| H-10 | 020 | `users` / `doctors` / `departments` PUT/DELETE 不存在 → `404`；科室仍有关联医生时删除 → **`409`** | `FUNCTIONAL_SPEC.md:1220-1225`（科室删除保护存在，仅语义收紧）；2.5 表格未声明存在性 | `server/api/v1/users.py:175,194,210`；`server/api/v1/doctors.py:210,230,246`；`server/api/v1/departments.py:136,158,160` | http-contract |
| H-11 | §3.6 架构性变更 | **业务失败表达（SPEC 强制修复，非「有意偏离 legacy」）**：legacy 的 `HTTP 200 + body.code=400` 是错误设计，`SPEC.md` §3.6「业务失败的表达」/ §5.1「错误承载」明文禁止、AC-B-43 断言；现行为 = 真实 HTTP 状态码 + 与之一致的 `code`。H-11 是 H-1…H-10 的**共享上层** | `FUNCTIONAL_SPEC.md:198-200,1488`（错误设计，非应保留行为） | `server/core/errors.py:10-27`；`server/core/response.py` | http-contract |
| H-12 | 020 | `PUT /users/{id}/status` 请求形态：**query 参数 → JSON body**（`{status:int}`） | `FUNCTIONAL_SPEC.md:336`（明确标注「`status` 走查询参数」） | `server/api/v1/users.py:61-62`（路由 PUT `/users/{user_id}/status`） | http-contract |

> **H-11 / H-12 为本册新增**（你给的清单未列），已按决策保留：H-11 是 H-1…H-10 的共同上层，
> 见下节；H-12 是同类里唯一的请求形状变更。

### H-11 与 H-1…H-10 的关系（024 的应用顺序）

024 对比时**先应用 H-11，再逐端点应用 H-1…H-10**：

- **H-11（共享上层，整体豁免）**：所有端点的失败响应形状从 `HTTP 200 + body.code` 改为
  真实 HTTP 状态码 + 同码 `code`。这是一次性、全局的响应形状修复，**不逐端点重复登记**。
- **H-1…H-10（具体端点语义，逐条）**：在 H-11 已生效的前提下，各端点的状态码取值
  （`404` / `409`）与存在性收紧。024 对每个端点先按 H-11 接受「失败不再走 200」，
  再按对应 H-* 接受该端点的 `404` / `409`。

## URL scheme 的整体权威（说明性条目，不逐行登记）

| ID | 事项 | 权威 | 说明 |
|---|---|---|---|
| D-1 | 端点 URL 方案整体以 `SPEC.md` §5.4 为准（legacy 的 `/users/list`、`/consult/create`、`/graph/subgraph`、`/graph/full` 等一律作废） | `SPEC.md` §5.4；对照 `FUNCTIONAL_SPEC.md:271,313-316,330-345,358-359,395-396` | 属 SPEC §5.4 契约本身，**不逐行登记端点路径**。024 的契约测试按 §5.4 整表校验；本行仅供对照，**不计入偏离条目数** |

> D-2（`PUT /doctors/{id}/status` 是否 query→body）**不登记**：legacy 仅为 users 版
> 标注「走查询参数」（`FUNCTIONAL_SPEC.md:336`），医生版（`:342`）未标注，无 divergence 可登记。

## 已核对、确认**非**偏离（供 023/024 对照，避免误加）

| 项 | 结论 | 证据 |
|---|---|---|
| 会话消息归属 | 保持现状：`GET /chat/sessions/{id}/messages` 只校验会话存在、不校验归属 | `server/api/v1/chat.py:224-232`；`FUNCTIONAL_SPEC.md:1516`；`SPEC.md` §7.2「原样保留」 |
| 公开图谱只读端点 | 保持公开，不收紧 | `SPEC.md` §7.2；`server/api/v1/graph.py` 四个公开端点 |
| 状态迁移无校验 | 保持现状（写入请求给定的状态值） | `FUNCTIONAL_SPEC.md:1192`；`SPEC.md` §7.3 |
| 科室删除只校验医生不校验预约 | 保持现状 | `FUNCTIONAL_SPEC.md:1225,1538` |
| 账号/科室 `doctor_count` 口径、公开医生列表过滤 | 与 legacy 一致 | `FUNCTIONAL_SPEC.md:324-326`；`server/repositories/departments.py` |

## 变更记录

- 2026-10-04：建档（TICKET-023 开工前置）。收录 a–k + §3.6 六条 + 新增 H-11/H-12 +
  存疑 D-1/D-2 + 非偏离对照。
- 2026-10-04：按决策处理——H-11 改述为「SPEC 强制修复」并声明其与 H-1…H-10 的分层与
  024 的应用顺序；H-12 保留；D-1 改为「URL scheme 整体权威」说明性条目（不逐行登记、
  不计入条目数）；D-2 不登记。
