# SKILL: symptom-normalization（症状归一化 / 确定性能力 Skill）

| 项 | 值 |
|---|---|
| 类别 | 确定性能力 Skill |
| 编排顺位 | 第 2 位；安全门放行后**恒执行** |
| 大模型调用 | 无 |
| Schema 版本 | `symptom-normalization-schema-v1` |
| 词表版本 | `symptom-vocabulary-v1` |
| 实现 | `server/skills/symptom_normalization/`（`skill.py`、`vocabulary.py`） |
| 契约权威来源 | 本文件。本文件四节与运行时行为一致；不一致以实现或本文件的修正为准，不得两处并存矛盾。 |

本 Skill 是一个**后端确定性运行时组件**，通过统一协议 `invoke(input) → output` 被调用
（seam B-2，`skills/protocol.py`）。它把患者的口语描述映射到图谱标准症状名。检测为纯 CPU
的字符串处理，不访问任何外部资源、不调用大模型，因此同一输入的结果可复现。

本 Skill 解决的正是 `SPEC.md` 第 3.6 节「有意修复」的第一项：旧实现里「30 词提取表」与
「22 条别名表」割裂、21 条别名在对话链路永远不可达。现在**只有一份词表**，对话链路与症状
推理链路同等生效。

---

## 1. 输入输出 Schema

### 1.1 输入 `SymptomNormalizationInput`

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---|---|---|
| `message` | `string` | 是 | 长度 ≥ 1 | 患者本轮问诊的原始描述文本，原样传入，不做预归一化 |

示例：

```json
{"message": "我头疼发烧三天了"}
```

约束语义：

- `message` 为空串时，B-2 协议判定为 `invalid_input`，`run()` 不被调用，不产出症状集合。
- 输入只有 `message` 一个字段。结构化症状列表的归一化走同一份词表的 `normalize_terms()`
  （见 1.5 节），由症状推理链路直接复用。

### 1.2 输出 `SymptomNormalizationOutput`

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---|---|---|
| `vocabulary_version` | `string` | 是 | 非空，等于词表版本 | 本次归一化依据的词表版本号 |
| `symptoms` | `string[]` | 是 | 可为空数组 | 标准症状集合，按**首次出现位置**排序、已去重 |

输出示例：

```json
{"vocabulary_version": "symptom-vocabulary-v1", "symptoms": ["头痛", "发热"]}
```

`symptoms` 为空数组是合法输出（例如「你好」），表示本次输入不含任何可识别的标准症状；
编排据此跳过图谱推理（`SPEC.md` 6.1 AC-B-23）。

### 1.3 唯一词表（标准词 + 别名）

**唯一来源**：`server/skills/symptom_normalization/vocabulary.py`，常量 `SYMPTOM_TERMS`。
这是全项目**唯一一份**症状词表：既含标准词，也含口语别名与否定式规则。对话链路与症状推理
链路都从这里取词，代码库中不存在第二份提取表或别名表（`SPEC.md` 6.1 AC-B-17）。

下表口语输入沿用 `FUNCTIONAL_SPEC.md` 5.1 的 22 条别名映射，映射目标沿用其 14 个标准症状：

| 口语输入（别名） | 归一化为（标准症状） |
|---|---|
| `头疼` | `头痛` |
| `头胀` | `头痛` |
| `头昏` | `头晕` |
| `发烧` | `发热` |
| `发高烧` | `发热` |
| `高烧` | `发热` |
| `低烧` | `发热` |
| `肚子痛` | `腹痛` |
| `胃疼` | `腹痛` |
| `胸口闷` | `胸闷` |
| `疲倦` | `乏力` |
| `想吐` | `恶心` |
| `拉肚子` | `腹泻` |
| `关节疼` | `关节痛` |
| `腰疼` | `腰痛` |
| `看不清` | `视力模糊` |
| `流鼻涕` | `流涕` |
| `喉咙痛` | `咽痛` |
| `嗓子痛` | `咽痛` |
| `胸口痛` | `胸痛` |
| `没力气` | `乏力` |
| `疲劳` | `乏力` |

除上表的别名外，词表还包含旧「提取表」中的其余标准症状（`FUNCTIONAL_SPEC.md` 5.2：
`咳嗽`、`呕吐`、`心悸`、`失眠`、`皮疹`、`瘙痒`、`水肿`、`出血`、`耳鸣`、`鼻塞`、
`高血压`、`糖尿病`、`感冒`、`过敏`、`便秘`、`尿频` 等）以及别名目标中缺失的 `胸痛`。
它们在两条链路中都生效。匹配规则为**子串包含**，从原文提取时不做分词、不做同义扩展、
不做大小写或繁简转换；输出按各表面词**首次出现位置**排序。

### 1.4 否定式规则

| 项 | 值 |
|---|---|
| 判定窗口 | 命中片段之前紧邻的最多 5 个字符 |
| 否定标记 | `没有`、`否认`、`并非`、`并不`、`从未`、`不曾`、`未见`、`未出现`、`不伴有`、`不伴`、`毫无`、`排除`、`没`、`无`、`未`、`不` |
| 判定 | 窗口以任一否定标记**结尾**即视为否定，该次命中不计入 |
| 作用范围 | 只作用于紧邻的这一次命中；跨标点不延伸 |

与安全门（TICKET-003）使用同一保守规则：宁可漏归一化一个被否定的症状，也不把否定表述
当成症状。例：「没有头疼」→ `[]`；「没有头疼，但是肚子痛」→ `["腹痛"]`。

### 1.5 seam 签名（供其他 Skill 复用）

词表模块对外暴露三个形状；除 B-2 协议外，这就是本 Skill 的公开契约：

```python
# server/skills/symptom_normalization/vocabulary.py
VOCABULARY_VERSION: str
SYMPTOM_TERMS: tuple[SymptomTerm, ...]      # SymptomTerm(standard, surfaces)
STANDARD_SYMPTOMS: tuple[str, ...]

def extract_symptoms(text: str) -> list[str]        # 对话链路：原始文本 → 标准症状集合
def normalize_terms(terms: Sequence[str]) -> list[str]  # 症状推理链路：显式症状列表 → 标准症状集合
```

- `extract_symptoms`：从自由文本里按词表子串匹配，返回按首次出现位置排序、去重、剔除否定
  的标准症状集合。`SymptomNormalizationSkill.run()` 直接调用它。
- `normalize_terms`：对显式症状列表逐项处理；已知表面词（含别名）替换为标准词，未知词按原
  样保留（维持既有 `/graph/infer` 行为），保持首次出现顺序并去重。**与 `extract_symptoms`
  共用同一份 `SYMPTOM_TERMS`**，因此同一输入在两条链路得到同一标准症状集合
  （`SPEC.md` 6.1 AC-B-18）。
- 图谱推理 Skill（TICKET-006）与编排（TICKET-007）只能通过这两个函数取词，不得自带词表。

---

## 2. 触发条件

| 项 | 内容 |
|---|---|
| 何时被调用 | 安全门放行（`decision == "allow"`）后**恒执行**，位于检索与图谱推理之前 |
| 何时被跳过 | 安全门拦截（`decision == "intercept"`）导致全链路短路时，本 Skill 不被调用（TICKET-008） |
| 被跳过时写入 trace 的理由 | 由编排在 `skills_skipped` 中注入（如 `safety-gate intercepted`）；本 Skill 自身不产出该记录 |
| 大模型调用 | 无。本 Skill 不声明、不接收任何外部端口 |

### trace 与审计

通过 B-2 协议调用时，每次调用恰好产生一条 span：

| 字段 | 值 |
|---|---|
| `name` | `symptom-normalization` |
| `status` | `ok`（正常产出症状集合）/ `error`（输入非法或内部异常） |
| `input_digest` | 输入的受限摘要（`SPEC.md` 3.7） |
| `output_digest` | 输出的受限摘要，含 `vocabulary_version` 与标准症状集合 |

---

## 3. 边界情况

| 情况 | 确定性处置 |
|---|---|
| 空输入（`message` 缺失或为空串） | B-2 协议判定 `invalid_input`；`output` 为 `null`，`error` 非空；写入一条 `status == "error"` 的 span。不请求大模型 |
| 无可识别症状（如「你好」「想咨询一下」） | 返回 `symptoms == []`，`status == "ok"`；不是错误，由编排决定跳过图谱支路 |
| 超长输入 | 不做截断，按同一子串规则扫描全文；只影响 `input_digest`（受限摘要），不影响结果 |
| 外部依赖不可用 | 不适用。本 Skill 零外部依赖、零端口，不访问数据库、图库、向量索引或大模型 |
| 否定式表述（「没有头疼」「不发烧」） | 不计入症状集合（见 1.4 节） |
| 否定与未否定共存（「没有头疼，但是肚子痛」） | 被否定的那次命中跳过，未否定的照常计入 |
| 同一症状多次出现 | 去重，并保留**首次出现位置**；多次命中只留一项 |
| 别名与标准词同时出现（「头疼和头痛」） | 合并为一项（`头痛`）；同一标准词的不同表面词不重复计入 |
| 未知症状词（症状推理链路传入 `牙痛`） | 词表中查不到时按原样保留（维持既有 `/graph/infer` 行为）；`extract_symptoms` 不会产出未知词 |
| 同一输入重复运行 | 结果完全一致；无随机数、无时间、无外部状态参与 |

---

## 4. 测试用例

下表每条用例都对应 `server/tests/test_symptom_normalization_skill.py` 中一个可直接执行的
测试，测试在 B-2 seam（`SymptomNormalizationSkill().invoke(...)`）与词表 seam
（`extract_symptoms` / `normalize_terms`）上断言，不触碰内部实现。

| 用例 | 输入 | 期望输出 | 对应测试 |
|---|---|---|---|
| 正例：口语症状归一化 | `头疼` / `肚子痛` / `拉肚子` / `嗓子痛` | 分别为 `["头痛"]` / `["腹痛"]` / `["腹泻"]` / `["咽痛"]`，均非空 | `test_colloquial_symptoms_normalize_to_standard_names` |
| 正例：多症状按出现位置输出 | `肚子痛，头疼` | `["腹痛", "头痛"]` | `test_symptoms_are_ordered_by_first_occurrence` |
| 边界：去重并保留首次位置 | `头疼，发烧，头胀` | `["头痛", "发热"]` | `test_duplicates_collapse_keeping_the_first_occurrence` |
| 边界：别名与标准词合并 | `头疼和头痛，还有发烧` | `["头痛", "发热"]` | `test_alias_and_standard_word_merge_into_one_entry` |
| 负例：否定式不计入 | `没有头疼，也不发烧，只是有点咳嗽` | `["咳嗽"]` | `test_negated_expressions_are_not_counted` |
| 边界：否定不掩盖未否定项 | `没有头疼，但是肚子痛` | `["腹痛"]` | `test_negation_does_not_mask_an_unnegated_mention` |
| 契约：两条链路一致 | 22 条别名逐条 | `extract_symptoms(别名) == normalize_terms([别名]) == [标准词]` | `test_chat_and_graph_chains_produce_the_same_standard_set` |
| 契约：唯一词表 | 全仓库 Python 源文件 | 只有 `vocabulary.py` 定义症状/别名表 | `test_the_vocabulary_is_the_only_symptom_and_alias_table` |
| 契约：文档与运行时一致 | 本文件 1.3 表 | 与 `SYMPTOM_TERMS` 的别名对完全一致 | `test_skill_md_alias_table_matches_the_runtime_vocabulary` |
| 边界：空输入 | `""`（或缺失 `message`） | `status == "invalid_input"`；`output is None`；一条 `status == "error"` 的 span | `test_empty_input_is_rejected_not_silently_continued` |
| 边界：无外部依赖 | `胸口痛`，同时注入「调用即抛异常」的大模型假实现 | 结果不变；`status == "ok"`；trace 中只有一条 `symptom-normalization` span | `test_runs_with_a_throwing_llm_port_in_scope` |
| 边界：确定性 | 同一输入连续运行 100 次 | 100 次结果完全一致 | `test_same_input_is_identical_over_100_runs` |
| 边界：未知词保留 | 症状推理链路传入 `牙痛` | `["牙痛"]` | `test_unknown_graph_terms_are_kept_verbatim` |
| 审计：trace 摘要 | `头疼发烧三天了` | span 的 `output_digest` 含 `vocabulary_version` 与全部标准症状 | `test_trace_digest_carries_the_normalized_symptoms` |
