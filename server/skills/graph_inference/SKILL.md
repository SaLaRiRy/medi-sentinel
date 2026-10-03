# SKILL: graph-inference（图谱推理 / 确定性能力 Skill）

| 项 | 值 |
|---|---|
| 类别 | 确定性能力 Skill |
| 编排顺位 | 第 3b 位；安全门放行、归一化完成后执行，与 vector-retrieval（3a）**并行** |
| 大模型调用 | 无 |
| Schema 版本 | `graph-inference-schema-v1` |
| 实现 | `server/skills/graph_inference/`（`skill.py`、`inference.py`） |
| 契约权威来源 | 本文件。本文件四节与运行时行为一致；不一致以实现或本文件的修正为准，不得两处并存矛盾。 |

本 Skill 是一个**后端确定性运行时组件**，通过统一协议 `invoke(input) → output` 被调用
（seam B-2，`skills/protocol.py`）。它把症状集合反查为可能疾病，按覆盖率排序后交给编排，
使医生与患者都能看到「依据了哪些症状、为什么排在前面」。推理不依赖大模型，可复现。

它只依赖 B-3 的窄端口之一 —— `GraphPort`。它**不**直接访问关系型数据库、图数据库或向量
索引，也**不**声明 `LlmPort`，因此可在不启动任何真实外部依赖的前提下被单独调用，且在
「大模型端口为抛异常假实现」时全部测试仍通过（`SPEC.md` 3.4、4.1）。

归一化复用 symptom-normalization 的**同一份词表**：本 Skill 的输入症状（可含口语别名）
先经 `normalize_terms()` 归一化，再查询图谱。因此同一输入在 `/chat/send` 链路
（`extract_symptoms`）与 `/graph/infer` 链路（本 Skill）产出同一标准症状集合
（`SPEC.md` 6.1 AC-B-18）。TICKET-004 挂账的「跨链一致性」由本 Skill 的公开 seam 直接承担。

与 `SPEC.md` 3.6「有意修复」的相关三条：

- **覆盖率与字段名**：对外字段为 `coverage`，值 = 命中数 ÷ 输入症状数，保留 2 位小数。旧实现
  的字段名（语义实为覆盖率）在本 Skill 与契约中一律不再出现。
- **科室缺失取值**：缺失时为 `null`，不是字符串 `"-"`（展示层的 `-` 由前端负责）。
- **截断规则显式化并写入 trace**：返回条数上限是显式常量，随输出字段 `limit` 进入 span 摘要，
  不存在静默截断。

---

## 1. 输入输出 Schema

### 1.1 输入 `GraphInferenceInput`

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---|---|---|
| `symptoms` | `string[]` | 是 | 至少 1 项 | 显式症状列表，可含口语别名；原样传入，由本 Skill 经 `normalize_terms()` 归一化 |

示例：

```json
{"symptoms": ["头疼", "发烧", "咳嗽"]}
```

约束语义：

- `symptoms` 缺失或为空数组时，B-2 协议判定为 `invalid_input`，`run()` 不被调用，
  不产出候选疾病，也不查询图数据库。
- 输入只有 `symptoms` 一个字段。返回条数上限与小数位是 Skill 的固定规则，不是调用方可变参数
  （见 1.4 节）。

### 1.2 输出 `GraphInferenceOutput`

字段顺序即序列化顺序。截断与取整参数（`limit`、`coverage_decimals`）与降级标记故意排在
候选之前，使有界的输出摘要在被截断后仍带着「按什么规则排序、截断、保留几位小数、是否降级」
这一审计信息（见第 2 节「trace 与审计」）。

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---|---|---|
| `limit` | `int` | 是 | ≥ 1 | 本次生效的候选条数上限（截断规则） |
| `coverage_decimals` | `int` | 是 | ≥ 0 | 覆盖率保留的小数位数 |
| `degraded` | `bool` | 是 | — | 图谱支路是否降级（图库不可用等） |
| `degraded_reason` | `string \| null` | 是 | `degraded == true` 时非空 | 降级原因摘要，供 trace 与排查 |
| `symptoms` | `string[]` | 是 | 可为空数组 | 本次实际查询所用的标准症状集合（归一化结果） |
| `candidates` | `DiseaseCandidate[]` | 是 | 可为空数组 | 候选疾病，按 1.4 节规则排序、截断 |

`DiseaseCandidate`（字段与 `contracts/sse-events.json` 的 `disease_candidate` 完全一致）：

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---|---|---|
| `disease` | `string` | 是 | 非空 | 疾病名 |
| `match_count` | `int` | 是 | ≥ 1 | 命中症状数（命中数） |
| `coverage` | `float` | 是 | `0 ≤ coverage ≤ 1` | 覆盖率 = `match_count ÷ len(symptoms)`，保留 2 位小数 |
| `department` | `string \| null` | 是 | — | 所属科室；缺失时为 `null` |
| `matched_symptoms` | `string[]` | 是 | 非空 | 该疾病解释的输入症状，顺序与输入症状一致 |

输出示例（正常命中两条）：

```json
{
  "limit": 10,
  "coverage_decimals": 2,
  "degraded": false,
  "degraded_reason": null,
  "symptoms": ["头痛", "发热", "咳嗽"],
  "candidates": [
    {"disease": "上呼吸道感染", "match_count": 2, "coverage": 0.67, "department": "呼吸内科", "matched_symptoms": ["头痛", "发热"]},
    {"disease": "偏头痛", "match_count": 1, "coverage": 0.33, "department": "神经内科", "matched_symptoms": ["头痛"]}
  ]
}
```

输出示例（无候选）：`candidates == []`，`degraded == false`，`status == "ok"`。无候选不是错误。

输出示例（降级）：

```json
{
  "limit": 10,
  "coverage_decimals": 2,
  "degraded": true,
  "degraded_reason": "RuntimeError: graph unavailable",
  "symptoms": ["头痛", "发热"],
  "candidates": []
}
```

### 1.3 图端口契约（B-3 `GraphPort`）

`GraphPort.infer_diseases(symptoms)` 返回一个疾病记录序列，每条记录是一个映射
（沿用旧 `GraphService.infer_diseases_by_symptoms` 的查询语义，`FUNCTIONAL_SPEC.md` 5.3）：

| 键 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `disease` | `str` | 是 | 疾病名（非空） |
| `matched_symptoms` | `Sequence[str]` | 是 | 该疾病关联到的症状节点名 |
| `department` | `str \| None` | 否 | 所属科室；旧数据可能给字符串 `"-"` 表示缺失 |

端口只负责「沿疾病-有症状-症状关系反查」，**不参与**命中数统计、覆盖率计算、排序与截断 ——
这些规则全部在本 Skill 内确定性完成，因此端口顺序不影响结果。查询本身必须走 Neo4j
**异步驱动**（`AsyncGraphDatabase`，`SPEC.md` 3.1）；本 Skill 只通过注入的端口调用，
测试注入内存假实现，不启动图库。

### 1.4 排序、覆盖率与截断规则（显式化）

| 规则 | 值 | 常量 |
|---|---|---|
| 命中症状口径 | 只保留本次归一化症状集合内的项，按输入症状顺序排列 | — |
| 排序键 | `match_count` 降序，**并列时疾病名升序** | — |
| 返回条数上限 | 10 | `MAX_CANDIDATES` |
| 覆盖率公式 | `match_count ÷ len(symptoms)`，四舍五入（`ROUND_HALF_UP`，非银行家舍入）保留 2 位小数 | `COVERAGE_DECIMALS` |
| 最低命中阈值 | 无 —— 命中 1 个症状的疾病也返回 | — |
| 科室缺失取值 | `null`（旧值 `"-"`、空串、缺失一律归一为 `null`） | `DEPARTMENT_MISSING` |
| 归一化后症状为空 | 直接返回空列表，不查询图数据库 | — |

- **无最低命中阈值**（`SPEC.md` 附：Skill 清单）：只要能解释输入症状中的至少 1 个，就产出候选。
- **并列顺序显式化**：同命中数的候选按疾病名升序，避免依赖查询结果的偶然顺序，保证回放可复现
  （`SPEC.md` 3.8「诊断漂移率」）。
- **截断规则显式化**：Skill 自己执行 `[:MAX_CANDIDATES]`，即便端口返回更多也只保留排序后的前 10 条；
  规则随输出字段 `limit` 回写，随 B-2 协议写入 span 摘要（`SPEC.md` 3.6「截断规则显式化并写入 trace」）。
- **提示词与回传前端的条数关系**：本 Skill 最多回传 10 条；编排（TICKET-007）拼接大模型上下文时
  **只取前 5 条**，而回传前端的 `done.graph` 保留全部最多 10 条。该上限声明在此，由编排实现。

### 1.5 seam 签名（供编排复用）

```python
# server/skills/graph_inference/inference.py
MAX_CANDIDATES: int          # 10
COVERAGE_DECIMALS: int       # 2
DEPARTMENT_MISSING: str      # "-"

class DiseaseCandidate(BaseModel):   # disease, match_count, coverage, department, matched_symptoms
    ...

def coverage_of(match_count: int, total_symptoms: int) -> float
def normalize_department(raw: object) -> str | None
def to_candidates(
    records: Sequence[Mapping[str, Any]], symptoms: Sequence[str]
) -> list[DiseaseCandidate]

# server/skills/graph_inference/skill.py
class GraphInferenceSkill(Skill):
    def __init__(self, graph: GraphPort) -> None: ...
```

- 编排只通过 `GraphInferenceSkill(graph=port).invoke(payload, context)` 调用本 Skill；
  `graph` 端口来自 B-3。
- `coverage_of` / `normalize_department` / `to_candidates` 是纯函数（纯 CPU、无 I/O），可在无任何
  真实外部依赖下单独测试，也可被编排复用来把端口结果投射到契约 `DiseaseCandidate`。

---

## 2. 触发条件

| 项 | 内容 |
|---|---|
| 何时被调用 | 安全门放行（`decision == "allow"`）且归一化输出**非空**时执行，与 `vector-retrieval` **并行** |
| 何时被跳过 | ① 安全门拦截导致全链路短路时（TICKET-008）；② 归一化输出为空时（`SPEC.md` 6.1 AC-B-23）。两种跳过都由编排在 `skills_skipped` 注入理由，本 Skill 自身不产出该记录 |
| 大模型调用 | 无。本 Skill 不声明、不接收 `LlmPort` |
| 外部依赖不可用 | 图库不可用时返回 `degraded`（`status == "ok"`），不抛错、不阻断问答 |
| 与检索的关系 | 与 `vector-retrieval` 各自独立产出结果，互不筛选、互不重排；仅由编排在上下文组装时并列拼接 |

### trace 与审计

通过 B-2 协议调用时，每次调用恰好产生一条 span：

| 字段 | 值 |
|---|---|
| `name` | `graph-inference` |
| `status` | `ok`（正常，含无候选与降级）/ `error`（输入非法或内部异常） |
| `input_digest` | 输入症状列表的受限摘要（`SPEC.md` 3.7） |
| `output_digest` | 截断与取整参数（`limit`、`coverage_decimals`）+ 降级标记 + 归一化症状 + 候选的疾病名/命中数/覆盖率 |

`limit` 与 `coverage_decimals` 排在输出字段最前，因此输出摘要一旦被截断，
「按什么规则截断、保留几位小数」这一审计信息优先保留。

---

## 3. 边界情况

| 情况 | 确定性处置 |
|---|---|
| 空输入（`symptoms` 缺失或为空数组） | B-2 协议判定 `invalid_input`；`output` 为 `null`，`error` 非空；写入一条 `status == "error"` 的 span。不查询图数据库、不请求大模型 |
| 归一化后为空（如 `["没有头痛"]`） | 返回 `symptoms == []`、`candidates == []`、`degraded == false`、`status == "ok"`；**不查询图数据库**（FUNCTIONAL_SPEC 5.3） |
| 无候选（端口返回空序列） | `candidates == []`、`degraded == false`、`status == "ok"`；不是错误，问答继续 |
| 图库不可用（端口抛异常） | 捕获异常，返回 `degraded == true`、`candidates == []`、`degraded_reason` 非空；`status == "ok"`，不抛错，问答继续 |
| 端口返回结构非法（缺 `disease` / `matched_symptoms`，或类型不符） | 与「图库不可用」走同一条降级路径：`degraded == true`，不阻断问答 |
| 记录命中的症状不在本次输入集合内 | 该症状不计入 `match_count`；记录剔除后无任何命中症状时，不产出该候选 |
| 端口返回条数超过上限 | 显式截断到排序后的前 `MAX_CANDIDATES` 条；`limit` 随输出回写 |
| 科室缺失 / 为旧值 `"-"` | `department == null`，不是字符串 `"-"` |
| 多个候选命中数相同 | 按疾病名升序排列（排序键显式化，结果可复现） |
| 未知症状词（词表外，如 `牙痛`） | 由 `normalize_terms` 按原样保留并照常查询端口（维持既有 `/graph/infer` 行为） |
| 口语别名输入 | 经 `normalize_terms` 归一化为标准症状后再查询，与 `/chat/send` 链路结果一致 |
| 不启动关系库 / 图库 / 向量索引 | 本 Skill 只依赖注入的 `GraphPort`；测试注入内存假实现即可调用，无需任何真实外部依赖 |
| 不构成大模型调用 | `LlmPort` 为抛异常假实现时本 Skill 全部测试仍通过 |
| 同一输入重复运行 | 结果一致；本 Skill 无随机数、无时间、无自身外部状态（一致性取决于端口） |

---

## 4. 测试用例

下表每条用例都对应 `server/tests/test_graph_inference_skill.py` 中一个可直接执行的测试。
测试在 B-2 seam（`GraphInferenceSkill(...).invoke(...)`）、纯函数 seam
（`coverage_of` / `normalize_department` / `to_candidates`）、B-3 端口（注入的假实现）与
契约 seam（`contracts/sse-events.json`）上断言，不触碰内部实现。

| 用例 | 输入 | 期望输出 | 对应测试 |
|---|---|---|---|
| 正例：按覆盖率排序 | 症状 + 端口返回 2 条命中 | 候选按 `match_count` 降序；`coverage == [0.67, 0.33]`（独立字面量） | `test_candidates_are_ranked_by_match_count_with_explicit_coverage` |
| 正例：覆盖率保留 2 位小数 | 命中数/总数组合 | `coverage_of(1, 3) == 0.33`、`coverage_of(2, 3) == 0.67` | `test_coverage_is_rounded_to_two_decimals` |
| 边界：四舍五入而非银行家舍入 | `1/8 = 0.125`、`5/8 = 0.625` | `0.13`、`0.63`（内置 `round()` 会给 `0.12`、`0.62`） | `test_coverage_rounds_half_up_not_bankers` |
| 边界：科室缺失返回 `null` | 记录缺 `department` / 为 `"-"` / 带空白 | `department == [None, None, "耳鼻喉科"]` | `test_missing_department_is_null_not_a_dash` |
| 契约：科室归一化纯函数 | `None` / `"-"` / 空白 / 正常值 | `None` / `None` / `None` / 去空白后的字符串 | `test_normalize_department_treats_missing_and_dash_as_null` |
| 边界：命中症状口径 | 端口返回含输入外症状 | `matched_symptoms` 只含输入集合内项，顺序与输入一致 | `test_matched_symptoms_are_the_input_symptoms_the_disease_explains` |
| 边界：无最低命中阈值 | 5 个输入症状，疾病只命中 1 个 | 照常返回，`coverage == 0.2` | `test_a_disease_matching_only_one_symptom_is_still_returned` |
| 边界：超过上限被截断 | 端口返回 12 条记录 | 只保留前 10 条；`limit == 10` | `test_candidates_beyond_the_limit_are_truncated_not_silently` |
| 审计：截断规则写入 trace | 正常输入 | span 的 `output_digest` 含 `limit` 与 `coverage_decimals` 的取值 | `test_trace_digest_records_the_truncation_rule` |
| 边界：图库不可用即降级 | 端口调用即抛异常 | `status == "ok"`；`degraded == true`；`candidates == []`；不抛错 | `test_unavailable_graph_degrades_without_raising` |
| 边界：端口记录结构非法 | 记录缺 `matched_symptoms` | 走同一条降级路径：`degraded == true`；`candidates == []`；`status == "ok"` | `test_malformed_record_degrades_instead_of_raising` |
| 边界：归一化后为空 | `["没有头痛"]` | `symptoms == []`、`candidates == []`、未调用端口、未降级 | `test_empty_normalized_symptoms_skip_the_graph_query` |
| 边界：未知症状词原样查询 | `["牙痛"]` | `symptoms == ["牙痛"]`，端口收到 `("牙痛",)` | `test_unknown_symptoms_are_queried_verbatim` |
| 边界：空输入 | `[]`（或缺失 `symptoms`） | `status == "invalid_input"`；`output is None`；一条 `status == "error"` 的 span | `test_empty_input_is_rejected_not_silently_continued` |
| 边界：不构成大模型调用 | 环境中存在「调用即抛异常」的大模型假实现 | 只用图谱端口即可运行；本 Skill 不持有任何大模型端口 | `test_graph_inference_does_not_call_the_llm_port` |
| 契约：两条链路一致（22 条别名） | 22 条别名逐条 | `extract_symptoms(别名) == Skill 输出 symptoms == [标准词]`，端口收到标准词 | `test_chat_and_graph_chains_produce_the_same_standard_set` |
| 边界：确定性 | 同一输入连续运行 100 次 | 100 次候选完全一致 | `test_same_input_is_identical_over_100_runs` |
| 契约：纯函数 seam 与 Skill 一致 | 同一批记录 | `to_candidates(records, symptoms)` 的投影与声明一致 | `test_to_candidates_is_the_pure_projection_the_skill_uses` |
| 契约：候选满足 SSE 契约 Schema | 正常输入 | 每条候选通过 `contracts/sse-events.json#/$defs/disease_candidate` 校验 | `test_each_candidate_satisfies_the_sse_contract_schema` |
| 契约：旧字段名不存在 | 运行时源码与契约 JSON | 旧字段名（语义为覆盖率）在 `skills`/`api`/`repositories`/`models` 与 `contracts` 中均不出现 | `test_probability_does_not_exist_in_runtime_code_or_contracts` |
| 契约：文档与运行时一致 | 本文件 1.4 的常量 | 与 `inference.py` 的常量、Schema 版本一致 | `test_skill_md_documents_the_runtime_constants` |
