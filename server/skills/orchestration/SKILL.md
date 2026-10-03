# SKILL: orchestration（编排 / 编排 Skill）

| 项 | 值 |
|---|---|
| 类别 | 编排 Skill（Agent 本体） |
| 编排顺位 | 第 4 位：包住前三个顺位，串起全部 Skill 与大模型调用 |
| 大模型调用 | **是，且全项目仅此一个** |
| Schema 版本 | `orchestration-schema-v1` |
| 提示词版本 | `orchestration-prompt-v1` |
| 实现 | `server/skills/orchestration/`（`skill.py`、`prompt.py`、`frames.py`） |
| 入口 | B-1：`Orchestrator.run(request, *, session_id, history)`，产出 SSE 帧异步流 |
| 契约权威来源 | 帧契约见 `contracts/sse-events.json`（C-1）与 `SPEC.md` 5.5；本文件四节与运行时行为一致，不得两处并存矛盾。 |

一次问诊的完整编排：生成 trace → 先过安全门 → 归一化 → 并行跑向量检索与图谱推理
→ 组装上下文 → 调用大模型流式生成 → 把全过程以 SSE 事件流推给前端
（`SPEC.md` 2.3）。它自己不访问任何外部资源：四个能力/规则 Skill 通过 B-2 协议调用，
图库、向量索引与大模型只通过 B-3 端口接入，测试与回放替换端口而不替换 B-1
（`SPEC.md` 4.1 B-1、4.4）。

---

## 1. 输入输出 Schema

### 1.1 输入

`ChatRequest`（HTTP 请求体，REST 契约 C-1）：

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---|---|---|
| `session_id` | `int \| null` | 否 | — | 传入时按「会话号 + 本人」定位会话，找不到则新建 |
| `message` | `string` | 是 | 长度 ≥ 1 | 患者本轮问诊的原始描述文本 |
| `explicit_symptoms` | `string[] \| null` | 否 | — | 结构化症状提示（可含口语别名），不参与安全门判定 |

`Orchestrator.run` 的其余输入（B-1 seam，非 HTTP 字段）：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `session_id` | `int` | 是 | 由会话规则解析后的会话号，写入 `session` 帧 |
| `history` | `ChatTurn[]` | 否 | 已排除本轮提问的历史消息（最多取最近 6 条），默认空 |
| `ports` | `OrchestrationPorts` | 构造期注入 | `graph` / `retrieval` / `llm` 三个 B-3 窄端口 |
| `sink` | `TraceSink` | 构造期注入 | B-4 追踪汇聚 |

### 1.2 输出：SSE 帧序列

帧形状以 `contracts/sse-events.json` 为准；正常路径（安全门放行）的帧序固定为：

```
session → trace → route → content × N → done
```

| 帧 | 出现次数 | 说明 |
|---|---|---|
| `session` | 第 1 帧，恰好 1 次 | `{type, session_id}` |
| `trace` | 第 2 帧，恰好 1 次 | `{type, trace_id}`；之后所有带 `trace_id` 的帧一致 |
| `route` | 恰好 1 次 | `{type, skills_run, skills_skipped}`，路由决策确定后立即发出 |
| `safety` | **正常路径 0 次** | 仅拦截路径出现，由 TICKET-008 实现 |
| `content` | 0..N 次 | 逐段增量；空字符串片段不发出 |
| `done` | 末尾，恰好 1 次 | 与 `error` 互斥 |
| `error` | 0 或 1 次 | 仅大模型生成失败时发出（`code == 503`），流以它结束 |

`route.skills_run` 顺序固定，与 `SPEC.md` 6.1 AC-B-22 一致：

```
["safety-gate", "symptom-normalization", "vector-retrieval", "graph-inference", "orchestration"]
```

当组装后的症状集合为空时，`graph-inference` 不进入 `skills_run`，改用
`skills_skipped: [{skill: "graph-inference", reason: "..."}]` 记录理由。

### 1.3 `done` 载荷的投影规则

`done` 必须满足契约 `additionalProperties: false`，因此 Skill 内部字段在投影时被裁掉：

| 载荷 | 来源 | 投影 |
|---|---|---|
| `references[]` | `VectorRetrievalOutput.references` | 只保留 `index` / `file_name` / `snippet`；`distance` 与 `context` 都不进入 `done`，但仍留在 Skill 输出与 trace 摘要（TICKET-005 挂账第 1 条） |
| `graph[]` | `GraphInferenceOutput.candidates` | 原样输出全部最多 10 条 `DiseaseCandidate` |
| `coverage_note` | 编排生成 | 图谱被跳过、或候选数超过提示词上限时给出确定性说明，否则 `null` |
| `degraded` | 两条支路的 `degraded` 标记 | 取值 `retrieval` / `graph`，正常路径为空数组 |
| `cost_time` | 编排计时 | 从进入 `run` 到发出 `done` 的整毫秒数 |
| `trace_id` | 本轮 trace | 与 `trace` 帧一致 |

### 1.4 路由与提示词组装规则（显式化）

| 规则 | 值 | 常量/位置 |
|---|---|---|
| 安全门输入 | 仅 `{"message": 患者原文}` | `skill.py` |
| 图谱输入症状 | `归一化(原文) ∪ 归一化(explicit_symptoms)`，首次出现顺序去重 | `_ordered_union` |
| 图谱跳过条件 | 上面这个并集为空 | `GRAPH_SKIPPED_REASON` |
| 检索询问 | 患者原文（不做归一化） | `VectorRetrievalSkill` 入参 |
| 并行性 | 检索与图谱 `asyncio.gather` 并发，互不筛选、互不重排 | `skill.py` |
| 安全约束条数 | 4 条，与 `FUNCTIONAL_SPEC.md` 5.4 逐字一致 | `SAFETY_CONSTRAINTS` |
| 历史截断 | 最多最近 6 条，且不含本轮提问 | `HISTORY_LIMIT` |
| 上下文注入位置 | 在「当前问题」段内的 `参考知识：` 之后、「用户问题：」之前 | `USER_PROMPT_TEMPLATE` |
| 图谱进提示词条数 | 前 5 条；回传前端的 `done.graph` 仍是全部最多 10 条 | `PROMPT_GRAPH_LIMIT` |
| 知识片段正文 | 命中分块的**整块正文** `RetrievalReference.context`（不是前 200 字符的引用项 `snippet`） | `knowledge_fragment` |
| 上下文兜底 | 向量与图谱均无结果时取「暂无相关知识库内容。」，模型仍被调用 | `CONTEXT_FALLBACK` |

### 1.5 seam 签名（对外复用）

```python
# server/skills/orchestration/skill.py
class ChatRequest(BaseModel):        # session_id?, message, explicit_symptoms?
    ...

@dataclass(frozen=True)
class OrchestrationPorts:            # B-3
    graph: GraphPort
    retrieval: RetrievalPort
    llm: LlmPort

class Orchestrator:
    def __init__(self, ports: OrchestrationPorts, sink: TraceSink) -> None: ...
    async def run(
        self, request: ChatRequest, *, session_id: int, history: Sequence[ChatTurn] = ()
    ) -> AsyncIterator[dict]: ...

# server/skills/orchestration/prompt.py
HISTORY_LIMIT: int          # 6
PROMPT_GRAPH_LIMIT: int     # 5
SAFETY_CONSTRAINTS: tuple[str, ...]          # 4 条
def build_context(references, candidates) -> str
def build_prompt(*, history, message, context) -> str

# server/skills/orchestration/frames.py
def reference_payload(reference) -> dict       # 不含 distance
def done_payload(...) -> dict
```

HTTP 侧另有 `server/api/v1/chat.py`：`POST /api/v1/chat/send` 把帧按
`data: <JSON>\n\n` 写出，返回 `text/event-stream; charset=utf-8`。

---

## 2. 触发条件

| 项 | 内容 |
|---|---|
| 何时被调用 | 每次 `POST /api/v1/chat/send` 请求，恰好一次 |
| 何时被跳过 | 从不跳过。它是编排本体，没有上层 Skill 来决定它的去留 |
| 被跳过时写入 trace 的理由 | 不适用 |
| 大模型调用次数 | 正常路径恰好 1 次（`LlmPort.stream`）；安全门拦截时为 0 次（TICKET-008） |
| 调用的 Skill 顺序 | 安全门恒首先；归一化在放行后恒执行；检索与图谱并行；随后才组装上下文与生成 |

### trace 与审计

一次正常问诊产生 **6 条 span**（`SPEC.md` 3.7 / 6.1 AC-E-01）：

| `name` | 来源 | `status` |
|---|---|---|
| `safety-gate` | B-2 调用安全门 | `ok` |
| `symptom-normalization` | B-2 调用归一化 | `ok` |
| `vector-retrieval` | B-2 调用检索 | `ok`（含无命中与降级） |
| `graph-inference` | B-2 调用图谱（未跳过时才有） | `ok`（含降级） |
| `orchestration` | B-1 本体 | `ok` / `error` |
| `llm` | 大模型调用 | `ok` / `error` |

另有 1 条路由记录（`RouteDecision`）：`skills_run`、`skills_skipped` 与跳过理由，
与 `route` 帧一致。`orchestration` span 的输出摘要含本轮路由、引用数、候选数、降级支路
与答案长度，足以回答「这一轮走了哪些 Skill、为什么」。

---

## 3. 边界情况

| 情况 | 确定性处置 |
|---|---|
| 归一化输出为空、且无 `explicit_symptoms` | 跳过 `graph-inference`，写入 `skills_skipped` 理由；检索与生成照常 |
| `explicit_symptoms` 非空而原文无标准症状 | 图谱支路按并集执行；`explicit_symptoms` 经同一份词表归一（别名同样生效） |
| `explicit_symptoms` 含红旗表述 | **不影响安全门**：安全门只读 `message`，结构化字段无法解除流程规则（见第 5 节 a） |
| `session_id` 指向不存在的会话或他人会话 | 新建会话，不报错（FUNCTIONAL_SPEC 5.7）；归属由 TICKET-012 的身份接入后再收紧 |
| 向量索引不可用 / 返回结构非法 | 检索 Skill 返回 `degraded == true`、`references == []`；`done.degraded` 含 `retrieval`；问答继续 |
| 图谱不可用 / 返回结构非法 | 同上，`done.degraded` 含 `graph`；问答继续（TICKET-009 的完整验收） |
| 大模型不可用或流中抛错 | 不产生 `done`；发出 `error` 帧（`code == 503`），`llm` span 记 `error`；助手消息不落库（TICKET-009） |
| 大模型返回空串片段 | 不发出内容帧；`content` 帧数可为 0，`done` 仍然发出 |
| 图谱候选超过 5 条 | 提示词只取前 5 条，`done.graph` 返回全部最多 10 条，`coverage_note` 说明该截断 |
| 两条支路均无结果 | 上下文取固定兜底文本，模型仍被调用 |
| 客户端中途断开 | 下游调用被取消，`cancelled` 状态的 span 与 409 并发控制由 TICKET-010 实现 |
| 同一输入、同一配置重复运行 | `skills_run` / `skills_skipped` 与 `done` 形状完全一致（无随机排序、无时间参与路由） |

---

## 4. 测试用例

下表每条用例都对应可执行测试，断言在 B-1 seam（`Orchestrator.run`）、B-3 端口
（注入的计数假实现）与 B-4（内存 sink）上进行，不触碰内部实现。

| 用例 | 输入 | 期望输出 | 对应测试 |
|---|---|---|---|
| 正例：正常路径帧序 | 「我头疼发烧三天了」 + 命中端口 | 帧序 `session → trace → route → content×2 → done`；无 `safety` 帧 | `test_normal_path_emits_session_trace_route_content_then_done` |
| 正例：五 Skill 路由 | 同上 | `skills_run` 恰含五个 Skill，顺序与 AC-B-22 一致；与路由记录一致 | `test_route_runs_all_five_skills_in_the_spec_order` |
| 边界：路由确定性 | 同一输入 + 同一配置跑 3 次 | 三次 `route` 帧完全相同 | `test_same_input_and_configuration_route_identically` |
| 正例：双支路独立输入 | 同上 | 检索询问原文；图谱收到标准化症状 `("头痛", "发热")` | `test_retrieval_and_graph_receive_independent_inputs` |
| 边界：双支路并行 | 两个端口在共享 barrier 上会合 | 并发通过 barrier；串行实现会超时失败 | `test_branches_run_in_parallel_not_back_to_back` |
| 契约：`distance` 被投影掉 | 2 条命中 | 每条 `reference` 字段恰为 `index`/`file_name`/`snippet` | `test_done_carries_references_without_the_internal_distance_field` |
| 正例：候选与覆盖率 | 2 条疾病记录 | `done.graph` 按覆盖率排序；`department` 缺失为 `null`；`coverage_note == null` | `test_done_carries_the_ranked_candidates_and_a_coverage_note` |
| 审计：span 完整性 | 正常路径 | 6 条 span：5 条 Skill + 1 条 `llm`，全部 `ok` 且同一 `trace_id` | `test_trace_has_five_skill_spans_and_one_llm_span` |
| 契约：帧满足 SSE Schema | 上述每种帧 | `contracts/sse-events.json` 逐帧校验通过 | `test_every_frame_satisfies_the_sse_contract` |
| 边界：归一化为空跳过图谱 | 「你好」 | `skills_run` 无图谱；`skills_skipped` 有理由；图谱端口 0 次调用；无图谱 span | `test_graph_is_skipped_when_the_combined_symptom_set_is_empty` |
| 边界：`explicit_symptoms` 消费口径 | 原文「我头疼」+ 显式`拉肚子` | 图谱收到 `("头痛", "腹泻")`；安全门输入摘要不含 `拉肚子` | `test_explicit_symptoms_feed_the_graph_branch_but_never_the_safety_gate` |
| 边界：显式症状单独触发图谱 | 原文「你好」+ 显式`头疼` | 图谱收到 `("头痛",)`，`skills_run` 含图谱 | `test_explicit_symptoms_alone_are_enough_to_reach_the_graph` |
| 正例：提示词组装 | 8 条历史 + 命中端口 | 4 条安全约束齐全；只保留最近 6 条历史；上下文位于 `参考知识：` 与 `用户问题：` 之间 | `test_prompt_follows_the_documented_assembly_rules` |
| 边界：图谱进提示词截断 | 6 条候选 | 提示词含前 5 条、不含第 6 条；`done.graph` 仍 6 条；`coverage_note` 非空 | `test_graph_context_is_capped_at_five_while_done_returns_all_candidates` |
| 边界：上下文兜底 | 两端口返回空 | 提示词含「暂无相关知识库内容。」 | `test_context_falls_back_when_both_branches_are_empty` |
| 正例：知识片段用整块正文 | 命中正文长度 > 200 | 提示词含 `[文档1] <整块正文>`；`done.references[0].snippet` 仍只有 200 字符且无 `context`/`distance` | `test_prompt_context_uses_the_whole_chunk_not_just_the_snippet` |
| 边界：大模型失败 | 大模型端口抛异常 | 流以 `error` 帧结束、无 `done`；`llm` span 为 `error` | `test_llm_failure_ends_the_stream_with_error_not_done` |
| 端到端：HTTP + 会话规则 | `POST /chat/send` | 200 + `text/event-stream`；帧序正确；`references`/`graph` 非空 | `test_chat_send_streams_the_documented_frames_as_sse` |
| 会话：标题生成 | 25 字 / 8 字消息 | 标题 = 前 20 字 + `...` / 原样 | `test_new_session_gets_its_title_from_the_first_20_characters`、`test_short_message_is_used_as_the_title_without_an_ellipsis` |
| 会话：消息计数 +2 | 一轮问答 | 会话含 user + assistant 两条；`message_count == 2`；助手消息带 `references_json`/`graph_json`/`cost_time` | `test_a_completed_turn_stores_both_messages_and_adds_two_to_the_count` |
| 会话：复用与累加 | 先建会话再带 `session_id` 提问 | `session` 帧回同一会话号；标题不变；计数累加到 4 | `test_an_existing_session_keeps_its_title_and_accumulates_messages` |
| 会话：历史取最近 6 条 | 8 条历史 + 本轮提问 | 提示词只含第 3..8 条，不含第 1、2 条与本轮提问 | `test_only_the_most_recent_six_prior_messages_reach_the_model` |
| 会话：未知会话号 | `session_id=999999` | 新建会话并正常结束，不报错 | `test_an_unknown_session_id_starts_a_new_session_instead_of_failing` |
| 契约：迁移与文档一致 | 空库 | `alembic upgrade head` 得到 `t_consult_session` / `t_consult_message` | `test_upgrade_head_creates_the_consult_store` |

---

## 5. 跨票挂账结算

以下四条是 TICKET-003/004/005/006 悬置、必须在本票拍板的事项。结论同时写入
`.scratch/medisentinel/issues/07-orchestration-normal-path.md`。

### a) `ChatRequest.explicit_symptoms` 是否被消费；安全门只看 `message` 如何定

**结算：消费，但只喂图谱支路；安全门只读 `message`，结构化字段永远不能解除流程规则。**

- 归一化输出与 `normalize_terms(explicit_symptoms)` 按首次出现顺序求并集，作为
  `graph-inference` 的输入；别名（如 `拉肚子` → `腹泻`）走同一份词表，不另建词表。
- 安全门输入恒为 `{"message": 患者原文}`（`SafetyGateSkill` 的 Schema 只有 `message`）。
  判定依据必须是患者自己的话，否则一个结构化字段就能绕过红旗检测，与
  `SPEC.md` 3.5「确定性、可审计、匹配原文片段」冲突。
- 图谱跳过条件因此定义为「并集为空」，而不是单看原文归一化结果；当未传
  `explicit_symptoms` 时二者等价，AC-B-23 照常成立。

### b) 向量检索的 `distance` 投影

**结算：在本票投影掉。** `RetrievalReference.distance` 保留在 Skill 输出与 trace 摘要里
（TICKET-005 要求逐条记录距离），但 `done.references[]` 只写 `index`/`file_name`/`snippet`，
因为契约 `reference` 是 `additionalProperties: false` 且不含 `distance`。
持久化的 `references_json` 也用同一投影，存储与 wire 形状一致。
实现：`skills/orchestration/frames.py::reference_payload`；断言：契约逐帧校验测试。

### c) trace 审计的结构化 detail

**结算：本票不解决，明确由 TICKET-011 承接。**
本票的审计能力仍走 TICKET-002 的既有形态：受限摘要 + 字段顺序（安全门把
`rule_version`/`red_flags[].id`/`matched_text` 排在输出最前，归一化/检索/图谱把
截断参数排在前面）。要回答「为什么走了这条路由」已经足够（`orchestration` span 的
输出摘要含 `skills_run`/`skills_skipped`/引用数/候选数/降级支路）。
`Span` 增加结构化 `detail` 字段、由可观测性接口读回，是 TICKET-011 的范围。

### d) Neo4j 依赖：真实驱动还是假端口

**结算：本票只走 B-3 端口，不引入 `AsyncGraphDatabase`。**

- 本票是编排票，B-1 的替身策略明确是「不替换 B-1，通过 B-3 替换外部依赖」
  （`SPEC.md` 4.1）。编排只依赖 `GraphPort` 接口，不需要知道驱动是否存在。
- 真实适配器要连着真实图库才有意义：`AsyncGraphDatabase` 会话、连接串、图谱 Schema
  属于 TICKET-013（图谱与知识库种子数据）落地时一并引入；向量索引与大模型适配器同理，
  分别随 TICKET-015 的向量化链路与模型配置落地。
- 因此 `create_app` 默认注入的是一组不可用端口（图/检索降级、生成返回 `error` 帧），
  测试与回放注入计数假实现，端到端断言在 B-1 上进行，不依赖任何外部进程。

### 复核中校正的一条既有语义

**上下文片段恢复为「[文档N] <整块正文>」。** `FUNCTIONAL_SPEC.md` 5.3 规定检索产出的
上下文片段用整块正文、只有引用项截到前 200 字符（`SPEC.md` 3.6「最终上下文与输出的内容规则不变」）。
TICKET-005 的 `RetrievalReference` 当时只带 `snippet`，编排无从取得整块正文；本票为它补上
`context` 字段（整块正文，只用于提示词），并像 `distance` 一样在 `done` 投影时裁掉。
`server/skills/vector_retrieval/SKILL.md` 已同步该字段与用例，wire 契约不变。

### 仍在本票之外、留给后续票的接口

| 项 | 归属 |
|---|---|
| `GET /api/v1/chat/sessions`、`GET /api/v1/chat/sessions/{id}/messages`（会话列表与历史，`SPEC.md` 5.4） | TICKET-014 的前端需要它们；读取端点不在本票清单内 |
| `/chat/send` 的 401 / 403 | TICKET-012（令牌身份接入，同时收紧 `t_consult_session.user_id`） |
| `/chat/send` 的 409 并发生成控制 | TICKET-010 |
| `/chat/send` 的 503 / 504 生成不可用 | TICKET-009 |
| `safety` 帧的字段映射（`critical` → `emergency`、`matched_text` → `matched_surface` 等） | TICKET-008 |
