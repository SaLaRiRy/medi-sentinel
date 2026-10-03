# 07: orchestration 编排 Skill：正常路径 SSE 编排

**What to build:** 一次问诊的完整编排：生成 trace、先过安全门、归一化、并行跑向量检索与图谱推理、组装上下文、调用大模型流式生成，并把全过程以 SSE 事件流推给前端。这是唯一调用大模型的 Skill。

**Blocked by:** 03（safety-gate）、04（symptom-normalization）、05（vector-retrieval）、06（graph-inference）

**Status:** done

- [x] `POST /api/v1/chat/send` 端到端流式问答可用；会话标题按前 20 字符 + 省略号生成，消息计数 +2，历史取最近 6 条
- [x] `session` 与 `trace` 必为前两帧且顺序固定；正常路径不出现 `safety` 帧；`done` 恰好一次；`done` 与 `error` 互斥且流以二者之一结束
- [x] 正常路径 `skills_run` 恰好包含五个 Skill；同一输入同一配置下路由完全一致
- [x] 归一化输出为空时跳过图谱推理，并在 `skills_skipped` 中给出理由
- [x] 向量检索与图谱推理并行执行、互不筛选
- [x] 提示词组装规则与现状一致：安全约束 4 条、上下文注入位置、历史截断条数
- [x] 端到端场景「我头疼发烧三天了」：归一化产出含 `头痛`、`发热`；图谱返回候选疾病；`content` 帧非空；`done` 含引用与候选；trace 含 5 条 Skill span + 1 条大模型 span

## 交付物

- `server/skills/orchestration/`：B-1 入口（`skill.py`）、提示词组装（`prompt.py`）、帧投影（`frames.py`）、契约（`SKILL.md`）
- `server/api/v1/chat.py`：`POST /api/v1/chat/send` 的 SSE 出口 + trace 缓冲落库
- `server/services/chat.py`、`server/repositories/consult.py`、`server/models/consult.py`、迁移 `0003`：会话/消息规则与存储
- `contracts/openapi.json`：新增 `/api/v1/chat/send`
- 测试：`tests/test_orchestration_normal_path.py`（21 条）、`tests/test_chat_send_api.py`（6 条）

## 跨票挂账结算（本票拍板）

### a) `ChatRequest.explicit_symptoms` 的消费口径与安全门判定

**结论：消费，但只喂图谱支路；安全门只读 `message`。**

- 图谱输入 = `归一化(message) ∪ normalize_terms(explicit_symptoms)`，按首次出现顺序去重；别名走唯一词表。
- 安全门输入恒为 `{"message": 患者原文}`（其 Schema 只有 `message`）。结构化字段不能解除红旗规则，
  否则与 `SPEC.md` 3.5「确定性、可审计、匹配原文片段」冲突；安全门 trace 摘要里不出现任何 `explicit_symptoms` 内容。
- 图谱跳过条件据此定义为「并集为空」；未传 `explicit_symptoms` 时等价于「归一化输出为空」，AC-B-23 照常成立。
- 证据：`test_explicit_symptoms_feed_the_graph_branch_but_never_the_safety_gate`、`test_explicit_symptoms_alone_are_enough_to_reach_the_graph`。

### b) 向量检索 `distance` 的投影（005 挂账第 1 条）

**结论：在本票投影掉。** `distance` 保留在检索 Skill 输出与 trace 摘要中（005 要求逐条记录），
但 `done.references[]` 与落库的 `references_json` 都只含 `index`/`file_name`/`snippet`，
以满足契约 `reference` 的 `additionalProperties: false`。
证据：`test_done_carries_references_without_the_internal_distance_field`、契约逐帧校验测试。

### c) trace 审计的结构化 detail（003 挂账第 1 条）

**结论：本票不解决，明确由 TICKET-011 承接。** 本票沿用 TICKET-002 的摘要+字段顺序，
足以回答「走了哪些 Skill、为什么」；`Span` 增加结构化 `detail` 及可观测接口读回属 TICKET-011。

### d) neo4j 依赖：真实 `AsyncGraphDatabase` 还是假端口（006 挂账第 1 条）

**结论：只走 B-3 `GraphPort`，本票不引入 neo4j 依赖。**
编排的替身策略是「B-1 不动，通过 B-3 替换外部依赖」（`SPEC.md` 4.1）；真实异步驱动与图谱 Schema
随 TICKET-013 落地，向量索引/大模型适配器随 TICKET-015 落地。
`create_app` 默认注入不可用端口（检索/图谱降级、生成返回 `error` 帧），测试与回放注入计数假实现，
端到端断言不依赖任何外部进程。

## 移交 TICKET-008 的契约差异（本票发现）

安全门 Skill 输出的严重级是 `critical | urgent`、命中项字段是 `id/matched_text/level/label`；
而 SSE 契约 `safety` 帧要求 `level: emergency | urgent`、命中项字段 `id/label/matched_surface/severity`。
正常路径不发 `safety` 帧，故本票不涉及；TICKET-008 需要在编排层做这一步确定性映射，
并同步核对 `SPEC.md` 5.5 与 `safety_gate/SKILL.md` 的措辞。

## 复核中校正的一条既有语义

`FUNCTIONAL_SPEC.md` 5.3 规定：引用项截到前 200 字符，但拼进提示词的上下文片段是
「[文档N] <整块正文>」（`SPEC.md` 3.6「最终上下文与输出的内容规则不变」）。
TICKET-005 的 `RetrievalReference` 当时只带 `snippet`，编排拿不到整块正文。本票为它补上
`context` 字段（整块正文，只用于提示词），并像 `distance` 一样在 `done` 投影时裁掉；
wire 契约不变，`server/skills/vector_retrieval/SKILL.md` 已同步。

## 仍在本票之外、留给后续票的接口

| 项 | 归属 |
|---|---|
| `GET /chat/sessions`、`GET /chat/sessions/{id}/messages`（会话列表与历史） | TICKET-014 的前端需要；读取端点不在本票清单内 |
| `/chat/send` 的 401 / 403 | TICKET-012（令牌身份接入，同时收紧 `t_consult_session.user_id` 为外键） |
| `/chat/send` 的 409 并发生成控制 | TICKET-010 |
| `/chat/send` 的 503 / 504 生成不可用 | TICKET-009 |
