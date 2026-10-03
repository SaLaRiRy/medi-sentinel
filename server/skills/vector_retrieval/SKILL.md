# SKILL: vector-retrieval（向量检索 / 确定性能力 Skill）

| 项 | 值 |
|---|---|
| 类别 | 确定性能力 Skill |
| 编排顺位 | 第 3a 位；安全门放行、归一化完成后执行，与 graph-inference（3b）**并行** |
| 大模型调用 | 无（嵌入模型调用不算大模型生成调用） |
| Schema 版本 | `vector-retrieval-schema-v1` |
| 实现 | `server/skills/vector_retrieval/`（`skill.py`、`retrieval.py`） |
| 契约权威来源 | 本文件。本文件四节与运行时行为一致；不一致以实现或本文件的修正为准，不得两处并存矛盾。 |

本 Skill 是一个**后端确定性运行时组件**，通过统一协议 `invoke(input) → output` 被调用
（seam B-2，`skills/protocol.py`）。它把用户问句经向量索引检索为知识片段与引用来源，
供编排在 `done` 帧回传前端、并在需要时拼进回答上下文（`SPEC.md` 4.1 B-3、附：Skill 清单）。

它只依赖 B-3 的三个窄端口之一 —— `RetrievalPort`。它**不**直接访问关系型数据库、图数据库
或向量索引，也**不**声明 `LlmPort`：查询向量化发生在 `RetrievalPort` 之内，嵌入模型调用
不算大模型生成调用（`SPEC.md` 3.4）。因此本 Skill 可在不启动任何真实外部依赖的前提下被
单独调用，且在「大模型端口为抛异常假实现」时全部测试仍通过。

与 `SPEC.md` 3.6「有意修复」的两条相关：

- **降级不阻断**：向量索引不可用时返回 `degraded`，不是错误，问答继续，由编排在 `done`
  帧的 `degraded` 里标注支路 `retrieval`。
- **截断规则显式化并写入 trace**：条数上限与引用正文长度都是显式常量，并作为输出字段
  回写、随 B-2 协议进入 span 的摘要。

---

## 1. 输入输出 Schema

### 1.1 输入 `VectorRetrievalInput`

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---|---|---|
| `query` | `string` | 是 | 长度 ≥ 1 | 用于检索的问句（患者本轮原问，或编排拼接的检索问句） |

示例：

```json
{"query": "高血压平时要注意什么"}
```

约束语义：

- `query` 为空串或缺失时，B-2 协议判定为 `invalid_input`，`run()` 不被调用，不产出引用项。
- 输入只有 `query` 一个字段。条数上限与正文长度是 Skill 的固定规则，不是调用方可变参数
  （见 1.4 节）。

### 1.2 输出 `VectorRetrievalOutput`

字段顺序即序列化顺序。截断参数（`top_k`、`snippet_length`）与降级标记故意排在引用项之前，
使有界的输出摘要在被截断后仍带着「按什么规则截断、是否降级」这一审计信息（见第 2 节
「trace 与审计」）。

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---|---|---|
| `top_k` | `int` | 是 | ≥ 1 | 本次生效的检索条数上限（截断规则） |
| `snippet_length` | `int` | 是 | ≥ 1 | 引用正文截断长度（取前 N 字符） |
| `degraded` | `bool` | 是 | — | 检索支路是否降级（向量索引不可用等） |
| `degraded_reason` | `string \| null` | 是 | `degraded == true` 时非空 | 降级原因摘要，供 trace 与排查 |
| `references` | `RetrievalReference[]` | 是 | 可为空数组 | 引用来源，序号从 1 起、连续 |

`RetrievalReference`：

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---|---|---|
| `index` | `int` | 是 | 从 1 起、连续 | 引用序号，`done` 帧回传前端时的序号 |
| `file_name` | `string` | 是 | 非空 | 命中所属知识库文件名 |
| `snippet` | `string` | 是 | 长度 ≤ `snippet_length` | 命中分块正文的前 200 字符 |
| `distance` | `float` | 是 | — | 该条命中的距离（越小越近），**逐条记录** |

输出示例（正常命中两条）：

```json
{
  "top_k": 5,
  "snippet_length": 200,
  "degraded": false,
  "degraded_reason": null,
  "references": [
    {"index": 1, "file_name": "高血压防治指南.md", "snippet": "高血压患者应……", "distance": 0.12},
    {"index": 2, "file_name": "糖尿病健康管理.md", "snippet": "日常饮食应……", "distance": 0.35}
  ]
}
```

输出示例（无命中）：`references == []`，`degraded == false`，`status == "ok"`。无命中不是错误。

输出示例（降级）：

```json
{
  "top_k": 5,
  "snippet_length": 200,
  "degraded": true,
  "degraded_reason": "RuntimeError: vector index unavailable",
  "references": []
}
```

### 1.3 检索端口契约（B-3 `RetrievalPort`）

`RetrievalPort.search(query, top_k)` 返回一个命中序列，每条命中是一个映射，形状沿用旧
`VectorStore.search`（`FUNCTIONAL_SPEC.md` 2.3 / 5.5）：

| 键 | 类型 | 说明 |
|---|---|---|
| `content` | `str` | 命中分块正文 |
| `metadata` | `Mapping` | 至少含 `file_name: str`（分块所属文件名） |
| `distance` | `float` | 距离（余弦度量下的距离，越小越近） |

检索查询向量的嵌入发生在端口之内（旧 `AlibabaEmbeddings`，`FUNCTIONAL_SPEC.md` 5.5），
**不构成**本 Skill 的大模型调用：本 Skill 不接收、不调用 `LlmPort`。

### 1.4 截断规则与阈值（显式化）

| 规则 | 值 | 常量 |
|---|---|---|
| 最低命中阈值 | 无 —— 不按距离过滤 | — |
| 检索返回条数上限 | 5 | `RETRIEVAL_TOP_K` |
| 引用项正文长度 | 前 200 字符 | `SNIPPET_LENGTH` |

- **无最低命中阈值**（`SPEC.md` 附：Skill 清单）：端口返回的前 `top_k` 条命中**全部保留**，
  距离再大也不丢弃、不重排。
- **条数截断显式化**：Skill 自己执行 `hits[:RETRIEVAL_TOP_K]`，序号从 1 连续编造；即使端口
  返回条数超过上限，也只保留最前面的若干条。该规则不依赖端口是否自觉遵守 `top_k`。
- **正文截断显式化**：`snippet` 取分块正文前 `SNIPPET_LENGTH` 个字符，**不追加省略号**。
- 两者作为输出字段 `top_k`、`snippet_length` 回写，随 B-2 协议写入 span 的 `output_digest`
  （`SPEC.md` 3.6「截断规则显式化并写入 trace」）。

### 1.5 seam 签名（供编排复用）

```python
# server/skills/vector_retrieval/retrieval.py
RETRIEVAL_TOP_K: int          # 5
SNIPPET_LENGTH: int           # 200

class RetrievalReference(BaseModel):   # index, file_name, snippet, distance
    ...

def snippet_of(content: str, limit: int = SNIPPET_LENGTH) -> str
def to_references(hits: Sequence[Mapping[str, Any]]) -> list[RetrievalReference]

# server/skills/vector_retrieval/skill.py
class VectorRetrievalSkill(Skill):
    def __init__(self, retrieval: RetrievalPort) -> None: ...
```

- 编排只通过 `VectorRetrievalSkill(retrieval=port).invoke(query, context)` 调用本 Skill；
  `retrieval` 端口来自 B-3。
- `to_references` 与 `snippet_of` 是纯函数（纯 CPU、无 I/O），可在无任何真实外部依赖下单独测试，
  也可被编排复用来把端口结果投射到契约 `reference`（`index`、`file_name`、`snippet`）。

---

## 2. 触发条件

| 项 | 内容 |
|---|---|
| 何时被调用 | 安全门放行（`decision == "allow"`）且归一化完成后执行，与 `graph-inference` **并行** |
| 何时被跳过 | 安全门拦截导致全链路短路时（TICKET-008）本 Skill 不被调用；该跳过由编排在 `skills_skipped` 注入，本 Skill 自身不产出该记录 |
| 大模型调用 | 无。本 Skill 不声明、不接收 `LlmPort` |
| 外部依赖不可用 | 向量索引不可用时返回 `degraded`（`status == "ok"`），不抛错、不阻断问答 |
| 与图谱的关系 | 与 `graph-inference` 各自独立产出结果，互不筛选、互不重排；仅由编排在上下文组装时并列拼接 |

### trace 与审计

通过 B-2 协议调用时，每次调用恰好产生一条 span：

| 字段 | 值 |
|---|---|
| `name` | `vector-retrieval` |
| `status` | `ok`（正常，含无命中与降级）/ `error`（输入非法或内部异常） |
| `input_digest` | 检索问句的受限摘要（`SPEC.md` 3.7） |
| `output_digest` | 截断参数（`top_k`、`snippet_length`）+ 降级标记 + 引用序号/文件名 |

`top_k` 与 `snippet_length` 排在输出字段最前，因此输出摘要一旦被截断，
「按什么规则截断」这一审计信息优先保留。

---

## 3. 边界情况

| 情况 | 确定性处置 |
|---|---|
| 空输入（`query` 缺失或为空串） | B-2 协议判定 `invalid_input`；`output` 为 `null`，`error` 非空；写入一条 `status == "error"` 的 span。不请求大模型 |
| 无命中（端口返回空序列） | `references == []`、`degraded == false`、`status == "ok"`；不是错误，问答继续（上下文兜底由编排负责） |
| 向量索引不可用（端口抛异常） | 捕获异常，返回 `degraded == true`、`references == []`、`degraded_reason` 非空；`status == "ok"`，不抛错，问答继续 |
| 端口返回结构非法（缺 `content` / `metadata.file_name` / `distance`） | 与「索引不可用」走同一条降级路径：`degraded == true`，不阻断问答 |
| 端口返回条数超过上限 | 显式截断到前 `RETRIEVAL_TOP_K` 条；`index` 从 1 连续重编，不沿用端口原始序号 |
| 距离很大 / 无命中阈值 | 照常返回，不按距离过滤、不重排（无最低命中阈值） |
| 分块正文超过 200 字符 | `snippet` 取前 `SNIPPET_LENGTH` 个字符，不追加省略号 |
| 分块正文短于 200 字符 | `snippet` 原样返回 |
| 嵌入模型调用 | 发生在 `RetrievalPort` 之内，**不算**大模型生成调用；`LlmPort` 为抛异常假实现时本 Skill 全部测试仍通过 |
| 不启动关系库 / 图库 / 向量索引 | 本 Skill 只依赖注入的 `RetrievalPort`；测试注入内存假实现即可调用，无需任何真实外部依赖 |
| 同一输入重复运行 | 结果一致；本 Skill 无随机数、无时间、无自身外部状态（一致性取决于端口） |

---

## 4. 测试用例

下表每条用例都对应 `server/tests/test_vector_retrieval_skill.py` 中一个可直接执行的测试。
测试在 B-2 seam（`VectorRetrievalSkill(...).invoke(...)`）、纯函数 seam
（`to_references` / `snippet_of`）与 B-3 端口（注入的假实现）上断言，不触碰内部实现。

| 用例 | 输入 | 期望输出 | 对应测试 |
|---|---|---|---|
| 正例：返回知识片段与引用来源 | 问句 + 端口返回 2 条命中 | `references` 的 `index == [1, 2]`；逐条保留 `file_name`、`distance`；`snippet` 为正文前 200 字符 | `test_references_carry_index_file_name_snippet_and_distance` |
| 正例：正文截断到前 200 字符 | 命中正文长度 > 200 | `len(snippet) == 200` 且 `snippet == content[:200]` | `test_snippet_is_the_first_200_characters` |
| 边界：无命中仍是成功 | 端口返回 `[]` | `status == "ok"`；`references == []`；`degraded == false` | `test_no_hits_is_ok_with_empty_references` |
| 边界：无最低命中阈值 | 一条 `distance == 0.99`（很远）的命中 | 照常返回该条，不被过滤 | `test_a_far_hit_is_kept_because_there_is_no_threshold` |
| 边界：超过上限被截断 | 端口返回 8 条命中 | 只保留前 5 条；`index == [1, 2, 3, 4, 5]` | `test_hits_beyond_top_k_are_truncated_with_contiguous_indices` |
| 边界：索引不可用即降级 | 端口调用即抛异常 | `status == "ok"`；`degraded == true`；`references == []`；`degraded_reason` 非空；不抛错 | `test_unavailable_index_degrades_without_raising` |
| 边界：端口返回结构非法 | 命中缺少 `metadata.file_name` | 走同一条降级路径：`degraded == true`；`references == []`；`status == "ok"` | `test_malformed_hit_degrades_instead_of_raising` |
| 边界：不构成大模型调用 | 环境中存在「调用即抛异常」的大模型假实现 | 只用检索端口即可运行；本 Skill 不持有任何大模型端口 | `test_retrieval_does_not_call_the_llm_port` |
| 边界：空输入 | `""`（或缺失 `query`） | `status == "invalid_input"`；`output is None`；一条 `status == "error"` 的 span | `test_empty_input_is_rejected_not_silently_continued` |
| 审计：截断规则写入 trace | 正常输入 | span 的 `output_digest` 含 `top_k` 与 `snippet_length` 的取值 | `test_trace_digest_records_the_truncation_rule` |
| 契约：文档与运行时一致 | 本文件 1.4 的常量 | 与 `retrieval.py` 的常量、Schema 版本一致 | `test_skill_md_documents_the_runtime_constants` |
| 契约：纯函数 seam 与 Skill 一致 | 同一批命中 | `to_references(hits)` 与 Skill 输出一致 | `test_to_references_matches_the_skill_output` |
| 边界：确定性 | 同一输入连续运行 100 次 | 100 次的 `references` 与 `degraded` 完全一致 | `test_same_input_is_identical_over_100_runs` |
