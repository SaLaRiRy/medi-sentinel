# SKILL: safety-gate（安全约束 / Process Rules Skill）

| 项 | 值 |
|---|---|
| 类别 | Process Rules Skill |
| 编排顺位 | 第 1 位，**恒首先执行**，位于任何大模型调用之前 |
| 大模型调用 | 无 |
| Schema 版本 | `safety-gate-schema-v1` |
| 规则版本 | `safety-gate-rules-v1` |
| 实现 | `server/skills/safety_gate/`（`skill.py`、`rules.py`） |
| 契约权威来源 | 本文件。本文件四节与运行时行为一致，不一致以实现或本文件的修正为准，不得两处并存矛盾。 |

本 Skill 是一个**后端确定性运行时组件**，通过统一协议 `invoke(input) → output` 被调用
（seam B-2，`skills/protocol.py`）。它把患者原始描述按固定的红旗规则表做子串匹配，
命中即返回拦截决策，否则放行。检测不依赖大模型，不访问任何外部资源，因此结果可复现。

---

## 1. 输入输出 Schema

### 1.1 输入 `SafetyGateInput`

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---|---|---|
| `message` | `string` | 是 | 长度 ≥ 1 | 患者本轮问诊的原始描述文本，原样传入，不做预归一化 |

示例：

```json
{"message": "胸口剧痛，出冷汗，喘不上气"}
```

约束语义：

- `message` 为空串或缺失时，B-2 协议判定为 `invalid_input`，`run()` 不被调用，不产出决策。
- 输入只有 `message` 一个字段。`explicit_symptoms` 等结构化字段的检测接入由编排决定
  （见第 3 节「边界情况」），不在本 Skill 的输入契约内。

### 1.2 输出 `SafetyGateOutput`

字段顺序即序列化顺序；前三个字段构成审计三元组，故意排在最前，使有界的输出摘要在截断后
仍带着命中标识、匹配片段与规则版本（见第 2 节「trace 与审计」）。

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---|---|---|
| `rule_version` | `string` | 是 | 非空 | 本次判定依据的规则版本号 |
| `red_flags` | `RedFlagMatch[]` | 是 | 可为空数组 | 命中的全部红旗，顺序与规则表顺序一致，按 `id` 去重 |
| `level` | `"urgent" \| "emergency" \| null` | 是 | 无命中时为 `null` | 全部命中项中的**最高**严重级 |
| `decision` | `"intercept" \| "allow"` | 是 | 有命中即 `intercept` | 拦截或放行 |
| `message` | `string` | 是 | `decision == "intercept"` 时非空 | 面向患者的安全提示 |
| `suggested_action` | `string` | 是 | `decision == "intercept"` 时非空 | 面向患者的建议动作 |

`RedFlagMatch`：

| 字段 | 类型 | 必填 | 约束 | 说明 |
|---|---|---|---|---|
| `id` | `string` | 是 | 非空，规则表中唯一 | 红旗标识 |
| `matched_surface` | `string` | 是 | 非空，为 `message` 的子串 | 命中的原文片段（即命中的规则词） |
| `severity` | `"urgent" \| "emergency"` | 是 | — | 该条红旗的严重级 |
| `label` | `string` | 是 | 非空 | 该条红旗的中文名，用于生成提示 |

`RedFlagMatch` 的字段名与冻结的 SSE 契约 `contracts/sse-events.json` 的 `safety.red_flags[]`
逐字一致（`id` / `label` / `matched_surface` / `severity`），因此可原样投影为 wire 载荷；
严重级用语同样取契约的 `emergency` / `urgent`，不另立词表（TICKET-008 结算）。

严重级次序：`emergency`（立即急诊）> `urgent`（尽快就医）。

输出示例（拦截）：

```json
{
  "rule_version": "safety-gate-rules-v1",
  "red_flags": [
    {"id": "chest-pain", "matched_surface": "胸口剧痛", "severity": "emergency", "label": "急性胸痛"},
    {"id": "dyspnea", "matched_surface": "喘不上气", "severity": "emergency", "label": "呼吸困难"}
  ],
  "level": "emergency",
  "decision": "intercept",
  "message": "检测到需要立即处理的急症信号：急性胸痛、呼吸困难。请立即拨打 120 或前往最近的急诊科，不要自行等待或自行用药。",
  "suggested_action": "立即拨打 120 或前往最近的急诊科就诊。"
}
```

输出示例（放行）：

```json
{
  "rule_version": "safety-gate-rules-v1",
  "red_flags": [],
  "level": null,
  "decision": "allow",
  "message": "",
  "suggested_action": ""
}
```

### 1.3 红旗规则表（`rules.py`）

统一的一份规则表，顺序即输出顺序。匹配规则为**子串包含**（`pattern in message`），
不使用分词、不做同义词扩展、不做大小写或繁简转换。

| # | `id` | `level` | 中文名 | 命中的规则词（子串） |
|---|---|---|---|---|
| 1 | `chest-pain` | `emergency` | 急性胸痛 | 胸痛 / 胸口痛 / 胸口疼 / 胸口剧痛 / 胸部剧痛 / 心前区疼痛 / 心绞痛 / 压榨性疼痛 |
| 2 | `dyspnea` | `emergency` | 呼吸困难 | 喘不上气 / 喘不过气 / 上不来气 / 呼吸困难 / 呼吸急促 / 憋气 / 窒息 / 喘鸣 |
| 3 | `severe-headache` | `urgent` | 剧烈头痛 | 剧烈头痛 / 头疼欲裂 / 头痛欲裂 / 炸裂样头痛 / 雷击样头痛 |
| 4 | `stroke` | `emergency` | 卒中征象 | 口角歪斜 / 嘴歪 / 半身不遂 / 偏瘫 / 一侧肢体无力 / 言语不清 / 说话不清 / 口齿不清 / 突然不能说话 |
| 5 | `altered-consciousness` | `emergency` | 意识障碍 | 昏迷 / 意识不清 / 意识模糊 / 唤不醒 / 叫不醒 / 晕厥 / 昏倒 / 晕倒 / 抽搐 / 惊厥 / 不省人事 |
| 6 | `severe-bleeding` | `emergency` | 大出血 | 呕血 / 吐血 / 咯血 / 咳血 / 便血 / 血便 / 大出血 / 大量出血 / 阴道大出血 / 阴道出血 |
| 7 | `anaphylaxis` | `emergency` | 严重过敏 | 喉头水肿 / 喉咙肿胀 / 过敏性休克 |
| 8 | `poisoning-overdose` | `emergency` | 中毒/过量/自伤 | 中毒 / 服毒 / 药物过量 / 吃药自杀 / 割腕 / 自杀 / 喝了农药 |
| 9 | `severe-abdominal-pain` | `urgent` | 剧烈腹痛 | 剧烈腹痛 / 腹部剧痛 / 肚子剧痛 / 肚子疼得厉害 / 疼得直不起腰 |
| 10 | `pregnancy-emergency` | `urgent` | 孕期急症 | 孕期出血 / 怀孕出血 / 孕妇腹痛 / 孕期腹痛 |
| 11 | `black-stool` | `urgent` | 消化道出血征象 | 黑便 / 柏油样便 |

严重级不同时，`level` 取命中项中的最高级（`emergency` > `urgent`），并采用该级别的提示与建议动作。

---

## 2. 触发条件

| 项 | 内容 |
|---|---|
| 何时被调用 | **恒首先执行**，无前置条件。编排在拿到患者输入后第一件事就是调用本 Skill |
| 何时被跳过 | **从不跳过**。本 Skill 没有跳过分支，也没有降级分支 |
| 被跳过时写入 trace 的理由 | 不适用（不存在跳过路径） |
| 大模型调用 | 无。本 Skill 不声明、不接收任何外部端口 |
| 命中后的编排行为 | 由编排（TICKET-008）负责短路：不调用归一化、检索、图谱与大模型。本 Skill 只产出 `decision == "intercept"` |

### trace 与审计

通过 B-2 协议调用时，每次调用恰好产生一条 span：

| 字段 | 值 |
|---|---|
| `name` | `safety-gate` |
| `status` | `ok`（正常产出决策）/ `error`（输入非法或内部异常） |
| `input_digest` | 输入的受限摘要 |
| `output_digest` | 输出的受限摘要，**含审计三元组**：命中的红旗标识（`red_flags[].id`）、匹配到的原文片段（`red_flags[].matched_surface`）、依据的规则版本号（`rule_version`） |

`rule_version` 与 `red_flags` 排在输出字段最前（且每条命中项里 `id`、`matched_surface` 又排在
`severity`、`label` 之前），因此输出摘要一旦被截断，**优先保留**的正是审计三元组。

---

## 3. 边界情况

| 情况 | 确定性处置 |
|---|---|
| 空输入（`message` 缺失或为空串） | B-2 协议判定 `invalid_input`；`output` 为 `null`，`error` 非空；写入一条 `status == "error"` 的 span。不请求大模型 |
| 超长输入（很长的 `message`） | 不做截断，按同一子串规则扫描全文；只影响 `input_digest`（受限摘要），不影响判定 |
| 外部依赖不可用 | 不适用。本 Skill 零外部依赖、零端口，不访问数据库、图库、向量索引或大模型 |
| 否定式表述（「没有胸痛」「不发烧」） | 不触发。命中片段之前紧邻的窗口若以否定标记结尾（`没有` / `否认` / `并非` / `并不` / `从未` / `不曾` / `未见` / `未出现` / `不伴有` / `不伴` / `毫无` / `排除` / `无` / `没` / `未` / `不`），该次命中视为否定并跳过；否定只作用于紧邻的命中，跨标点不延伸 |
| 引述（如「我爷爷当年是胸痛走的」） | 与普通描述同等对待，仍会命中。这是安全侧偏向：宁可误拦，不可漏拦 |
| 多条红旗同时命中 | 返回全部命中项，顺序与规则表一致，按 `id` 去重（同一规则多处出现只记一次，取首次出现） |
| 多条红旗严重级不同 | `level` 取最高严重级，`message` 与 `suggested_action` 采用最高级对应的措辞 |
| 否定与多命中共存（「没有胸痛，但是喘不上气」） | 被否定的那条跳过，未被否定的那条照常命中 |
| 命中项极多、摘要超限 | span 的输出摘要是 200 字符上限的**摘要**（SPEC.md 3.7），极端多命中时超出部分被截断；字段顺序保证截断优先丢弃 `label` 等补充信息，审计三元组（`id`、`matched_surface`、`rule_version`）优先保留。完整命中项仍可从 Skill 输出取得 |
| 同一输入重复运行 | `decision` 与 `red_flags` 完全一致；无随机数、无时间、无外部状态参与判定 |
| `explicit_symptoms` 等结构化输入 | 本 Skill 只检测 `message`。结构化字段是否纳入检测由编排（TICKET-007/008）决定，不在本票范围 |

---

## 4. 测试用例

下表每条用例都对应 `server/tests/test_safety_gate_skill.py` 中一个可直接执行的测试，测试在
B-2 seam（`SafetyGateSkill().invoke(payload, context)`）上断言，不触碰内部实现。

| 用例 | 输入 `message` | 期望输出 | 对应测试 |
|---|---|---|---|
| 正例：普通描述放行 | `我头疼发烧三天了，吃了退烧药也没好转` | `decision == "allow"`；`red_flags == []`；`level is None`；`message == ""` 且 `suggested_action == ""` | `test_plain_description_is_allowed` |
| 正例：急症描述拦截 | `胸口剧痛，出冷汗，喘不上气` | `decision == "intercept"`；`level == "emergency"`；`red_flags` 含 `chest-pain` 与 `dyspnea`；`message` 与 `suggested_action` 均非空 | `test_emergency_description_is_intercepted` |
| 负例：否定式不触发 | `没有胸痛，也不发烧，就是有点咳嗽` | `decision == "allow"`；`red_flags == []` | `test_negated_red_flags_do_not_intercept` |
| 边界：否定与多命中共存 | `没有胸痛，但是喘不上气` | `decision == "intercept"`；`red_flags` 只含 `dyspnea` | `test_negated_hit_does_not_mask_an_unnegated_one` |
| 边界：多命中取最高级 | `剧烈头痛，还吐血` | `decision == "intercept"`；`red_flags` 同时含 `severe-headache`（`urgent`）与 `severe-bleeding`（`emergency`），顺序与规则表一致；`level == "emergency"` | `test_multiple_hits_return_all_and_take_the_highest_level` |
| 边界：确定性 | 同一输入连续运行 100 次 | 100 次的 `decision` 与 `red_flags` 完全一致 | `test_same_input_is_identical_over_100_runs` |
| 审计：trace 记录审计三元组 | 含 `胸口剧痛，喘不上气` 的长文本 | span 的 `output_digest` 含每条命中项的 `id`、`matched_surface` 与 `rule_version` | `test_trace_digest_carries_the_red_flag_audit_trail` |
| 契约：输出用语与冻结契约一致 | `胸口剧痛，喘不上气` | `level == "emergency"`；`RedFlagMatch` 字段名恰为 `id`/`label`/`matched_surface`/`severity`；每条 `severity ∈ {emergency, urgent}` | `test_output_speaks_the_frozen_sse_contract_vocabulary` |
| 边界：空输入 | `""`（或缺失 `message`） | `status == "invalid_input"`；`output is None`；写入 `status == "error"` 的 span | `test_empty_input_is_rejected_not_silently_continued` |
| 边界：无外部依赖 | `胸口剧痛`，同时环境中存在「调用即抛异常」的大模型假实现 | 判定结果不变；`status == "ok"`；trace 中只有一条 `safety-gate` span | `test_runs_with_a_throwing_llm_port_in_scope` |
| 契约：文档与运行时一致 | — | 上表 1.3 的规则表与 `rules.py` 的 `RULES` 在 `id` 与 `level` 上完全一致 | `test_skill_md_rule_table_matches_the_runtime_rule_table` |
