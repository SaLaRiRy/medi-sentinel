# 10: 活库重录回归基线（只录数据）

**What to build:** `scripts/regression.py record` 增加 `--live` 路径：**从 scripts 侧注入真实
B-3 适配器**（`adapters.build_graph_store` / `build_vector_store` / `build_llm`），把一次真实
问诊（Neo4j 图谱 + 活库向量检索 + 真实模型）录成**新版本基线 v3**。这样
「红旗拦截率 / 误拦率」第一次由**真实测量**给出，而不是 `Fixture*` 替身的自证。

**只录数据**：不改判定层、不改编排、不改既有 v1 / v2。

**Blocked by:** 无（依赖 MySQL / Neo4j / 真实 API key 三样在线）

**Status:** done
Completed: e370da9

---

## 0. 立项依据（已实测，2026-10-11 探查）

`.tmp/probe_live_record.py`（gitignore，monkeypatch `record.fixture_ports`，未改生产文件）
在本机跑通三例：

| 用例 | 耗时 | 结果 |
|---|---|---|
| `高血压吃什么药` | **53.4 s** | 引用 5 条 / 候选 1 个 / 3277 字 / 600 帧 / 检索与 LLM 各 1 次调用 |
| `头疼还发烧，肚子也痛` | ≈85 s | 正常走完（整脚本 142 s 减去其余两例推得） |
| `胸口剧痛，出冷汗，喘不上气`（红旗） | **0.0 s** | 5 帧，只跑安全门 |

结论：**真实适配器确实能被录制路径包住并跑完**；瓶颈是模型流式生成，不是检索或图谱。

## 1. 范围

### 做

1. `regression/record.py`：`record_case` 与 `record_case_set` 各加一个**带默认值的关键字
   参数** `ports_factory: PortsFactory = fixture_ports`；`record_case` 内部把
   `graph, retrieval, llm = fixture_ports(case)` 改成 `ports_factory(case)`。
   外部 8 处测试调用 + 1 处 CLI 调用**全部不受影响**（都是位置调用 `record_case_set(case_set)`）。
2. `scripts/regression.py`：`record` 子命令加 `--live` 开关；打开时
   `from adapters import ...` 构造真实端口，传一个**返回同一批实例**的闭包
   （一个 Chroma store / 一个 Neo4j driver / 一个 LLM client，绝不逐条重连），
   并在收尾时统一 `close()`。
3. 新基线 **`regression/baselines/v3.json`**（以及配套的 `cases/v3.json`）。
4. `map.md` 在「已知局限」旁新增一小节，写清三份基线的**语义差异**：
   `v1` / `v2` = **fixture 替身语义**（`FixtureGraphPort` / `FixtureRetrievalPort` /
   `ScriptedLlmPort`）；`v3` = **真实调用快照语义**（真实 Neo4j / 活库向量检索 / 真实模型）。
   避免下一个人把三份基线当成同一种东西。

### 不做

- **不改幻觉判定层**（`regression/replay.py:55-62` 的上下文仍只由检索端口构建）——
  那是 AC-11 的范围。
- 不动 `v1` / `v2` 的任何字节。
- 不改 `regression/ports.py`：`regression/` 整包保持**零 adapter 依赖**，
  AST 测试（`test_regression_record_replay.py:169-179`）一个字不动。
- 不引入 `PatientContextPort` 之类的端口（档案走串行预取，见票 07）。

## 2. 分两个阶段，验收分开（**不要合成"录完 20 条"一个大验收**）

### 阶段一：只录 6 条红旗用例（先验收这一段）

理由：红旗用例实测 **0.0 秒**——只跑安全门、不打模型，几乎零 API 花费、零基线体积，
却能直接给出**真实测量**下的拦截率。

- [ ] `cases/v3.json` 先只放 v1 里的 6 条 `red_flag` 用例（`rf-chest-pain` /
      `rf-severe-bleeding` / `rf-altered-consciousness` / `rf-severe-headache` /
      `rf-fever-rash` / `rf-seizure`）。
- [ ] `record --case-set v3 --baseline-version v3 --live` 跑通，产出 `baselines/v3.json`。
- [ ] 回放这段基线：`redflag_intercept_rate == 1.0`、`redflag_false_positive_rate == 0.0`、
      `evidence_match_rate == 1.0`。
- [ ] 记录 `baselines/v3.json` 这一阶段的实际体积（应与 v1 的 6 条同量级）。

**反替身护栏**（防的是「录出来看着像真的、其实还是替身」）

- [ ] 6 条全部走 `intercept` 路径：`route.skills_run == ["safety-gate"]`、
      有 `safety` 帧、无 `content` 帧、`done.references == []`、`done.graph == []`。
- [ ] `trace_id` 是**本次运行生成的 32 位十六进制**（不是替身里可预期的固定串）。
- [ ] span 带非空 `started_at`，且 6 条各只有 1 条 span（安全门那条）。
- [ ] 阶段二的正常用例必须出现 **>0 次检索调用、>0 次图谱调用、≥1 个 LLM chunk**
      —— 那才是「真实链路确实被驱动」的证据。

⚠️ **红旗用例本来就是 0 次检索 / 0 次图谱 / 0 个 LLM chunk**（安全门命中即全链路短路），
所以「零 chunk」在阶段一是**预期**、不是录制失败——别读成"录坏了"。

**阶段一的能力边界（写进结论，不要含糊）**

- ✅ 证明：`--live` 注入路径打通、真实 adapter 能被构造并传入、CLI 守卫与 `--force` 生效、
  拦截率 / 误拦率确实由**本次真实录制**产出。
- ❌ **不能证明**：真实 Neo4j / 活库向量检索 / 真实模型三条链路在录制路径下可用——
  红旗用例在安全门就短路了。**已实测坐实**：同一套用例用替身录一遍，
  帧与真实录制**逐字一致**（归一化掉 `trace_id` 与 `cost_time` 后比较）。
  那三条链路只能由阶段二的正常用例证明。

**阶段一通过后再动阶段二。**

### 阶段二：补齐 14 条正常用例

这一步才背上 12–20 分钟录制、API 花费、多 MB 基线。

- [ ] `cases/v3.json` 补齐 v1 的其余 14 条（`llm` / `degraded` / `boundary` 组）。
- [ ] 重录 `v3`；`replay --compare v1 v3` 可跑，报告里 `case_count == 20`。
- [ ] **先量一条正常用例的实际体积**，再外推 20 条，然后按 §4.1 做决定。
- [ ] 幻觉率有非零分母（`hallucination.total > 0`），并**按 §3 条件标注**。
- [ ] `drift_rate` 有意义且可解释：候选疾病来自确定性图谱推理，不随模型波动。

## 3. 幻觉率必须带条件标注（选分票方案的核心）

阶段二产出的幻觉率，必须在**票面 / `spec.md` / `map.md` 三处**同时写上这段标注：

```
本次幻觉率由**确定性字面层**产出，其判定上下文**仅由检索端口构建**
（regression/replay.py:55-62），不含图谱片段——因此依据图谱结论的
疾病名/药品名/检查名会被判为无据。该缺陷未在本票修复，
故本数字**不等于**真实幻觉水平。
```

（修复与重算属 **AC-11**，等本票阶段二落地后再开。）

**这条缺陷的具体表现（可复现的靶子，AC-11 开工时直接用）**：
依据图谱结论说出的疾病名 / 药品名 / 检查名会被判无据。实测例子
（v3 的 `llm-explicit-symptoms` 用例）：

- 真实回答里有一条断言：`知识图谱初步提示：**慢性肾炎（覆盖率约0.50，科室：肾内科，依据症状：高血压）**`；
- 确定性层从这条断言里取到词表命中 `['高血压', '0.50']`；
- 判定上下文（**只由检索端口构建**）里没有「高血压」，于是整条被判**无据**；
- 但「高血压」恰恰是图谱候选（`infer_diseases` 的返回）里的节点名。

更短的一个（`llm-headache-alias`）：断言 `仅说"头疼"还不能判断具体原因，偏头痛、感冒/感染…`
命中词表 `感冒`，检索上下文里没有、图谱候选里有 `{"disease": "感冒"}`——同样被判无据。

全量实测：确定性层共评估 **400** 条断言，其中无据 **44** 条（11%），
而 44 条里有 **10 条**的缺失词出现在图谱结果里——这就是本缺陷的直接代价
（精确重算留给 AC-11，那 10 条是下界，不是全貌）。

## 4. 三条约束（写进实现与验收）

### 4.1 基线体积：先量一条，再决定，禁止"先录满才发现十几 MB"

- [ ] 录**一条**正常用例，量出 `baselines/v3.json` 的实际字节数并写进票面 Comments。
- [ ] 按 20 条外推（注意红旗用例几乎零体积）。
- [ ] 据此三选一并写明理由：① 直接进 git；② 压缩存储（`llm_chunks` 单独落文件或 gzip）；
      ③ 外置（不入库，只留录制脚本 + 校验值）。
- [ ] 已知参考：脚本化的 `baselines/v2.json`（20 条、无真实 chunk）是 **173 KB**；
      活库版每条约 600 个 chunk，量级完全不同。

### 4.2 快照语义：v3 不可由同一命令重新生成

票面与 `map.md` 都要写明：

```
v3 是某一次真实调用的快照，不可由同一命令重新生成（模型每次回答不同）。
回放逐字稳定——chunk 列表是被录下来的，因此 evidence_match_rate 与
replay --compare 不受影响。drift_rate 也仍然有意义：候选疾病来自
确定性图谱推理，不随模型波动。
```

### 4.3 录制入口防御：`--live` 不能覆盖既有基线

- [ ] `--live` 必须与显式 `--baseline-version` 同时出现
      （`--baseline-version` 现在已经是 `required=True`，本票要用**测试**把它钉住）。
- [ ] `--live` **拒绝写入已存在的基线文件**（明确报错 + 非零退出）——
      这样即便有人敲 `--live --baseline-version v1`，也覆盖不了 v1 / v2。
      要覆盖必须显式加 `--force`，该开关同样要有测试。
- [ ] 测试用假 `store` 目录，不碰已提交的 `baselines/`。

## 5. TDD 要点

| 用例 | 断言 |
|---|---|
| 注入点默认值 | 不传工厂时 `record_case_set(case_set)` 仍用 `fixture_ports`，既有 8 处调用零改动 |
| 注入生效 | 传假工厂 → 录制确实调用了它，且 `ports` 键里出现该工厂喂进去的响应 |
| 同一批实例 | 工厂被调用 N 次（N=用例数），但返回的是**同一组对象**（断言 `id()` 相同） |
| `--live` 缺版本号 | CLI 解析报错 / 非零退出 |
| `--live` 拒绝覆盖 | 目标基线已存在 → 非零退出 + 明确提示；加 `--force` 才写 |
| `--live` 未开 | 行为与现在完全一致（离线替身），既有录制测试全绿 |
| 回归包零依赖 | `regression/` 目录里搜 `adapters` / `neo4j` / `chroma` 零命中（沿用 AST 测试口径） |

## 6. 边界与坑

- **网络与外部依赖**：录制需要真实嵌入服务 + 模型 + Neo4j。沙箱内会被拦成
  `OpenAIConnectionError`（实测过）；失败现象是 `error` 帧 503 + `引用=0`，
  不是崩溃——排查时先看帧再怀疑代码。
- **成本**：阶段二要真的花 API 钱（14 条 × 完整回答）。建议先只录 1–2 条确认体积与
  耗时，再决定是否一次录满。
- **端点与后端**：走 `.env` 的 `OPENAI_BASE_URL`；默认后端是 `langchain`（票 09），
  必要时可用 `LLM_BACKEND=http` 对照，两者增量产出逐字相同。
- **别把 v3 说成"真实基线"就完事**：它的**拦截率/误拦率**是真数字，
  但**幻觉率**带 §3 那条缺陷（上下文不含图谱片段）。
- 录制是**串行**的（`record_case_set` 的列表推导），20 条就是这个耗时，别无谓并行。

## Comments

### 阶段一（2026-10-11）—— 已完成，等用户确认后进阶段二

**结果**

```
record --case-set v3 --baseline-version v3 --live
→ 已录制基线 v3（真实适配器）：6 条用例，耗时 1.0 s
→ baselines/v3.json：30,287 字节

replay --case-set v3 --baseline-version v3
→ redflag_intercept_rate 1.0 / redflag_false_positive_rate 0.0
→ evidence_match_rate 1.0 / case_count 6
→ hallucination.total 0（红旗用例无断言可评，预期）
```

**反替身护栏逐条断言**（取证脚本 `.tmp/verify_v3_phase1.py`，gitignore）：

| 护栏 | 实测 |
|---|---|
| 路由只有安全门 | 6/6 `skills_run == ["safety-gate"]` |
| 有 `safety` 帧、无 `content` 帧 | 6/6 帧序 `session → trace → route → safety → done`（各 5 帧）|
| `done.references == []` 且 `done.graph == []` | 6/6 |
| `trace_id` 是本次生成的 32 位十六进制 | 6/6（如 `28a7fa25…`）|
| span 带非空 `started_at`，各 1 条 | 6/6 |
| 0 LLM chunk / 0 检索 / 0 图谱调用 | 6/6（**红旗短路本来就是 0 次**：预期，不是失败）|

**能力边界（已实证坐实）**：把同一套 `cases/v3.json` 用**替身**再录一遍，逐条比较
归一化后的帧——**完全一致**。所以阶段一证明的是**注入路径打通**，不是"活库链路可用"；
真实 Neo4j / 检索 / 模型三条链路由阶段二证明。

**体积（§4.1 阶段一部分）**：红旗基线 30,287 字节 / 6 条 ≈ 5 KB/条，且这一档
**不含任何 LLM chunk**。真正要决定存储方式的是阶段二那条正常用例——按探查值
（单条 600 个 chunk）外推后再定，结论写进本 Comments。

**实现落点**（与 §1 / §4.3 一致）

- 注入点：`regression/record.py` 的 `PortsFactory` + `record_case` /
  `record_case_set` 的 `ports_factory`（带默认值：8 处测试 + 1 处 CLI 零改动）。
- 写守卫：`regression/schema.py` 的 `target_path` / `ensure_writable` /
  `write_baseline(force=)` —— **路径与判定只有一份**，CLI 不自己 `Path.exists()`；
  `_record` 在录制**之前**先问一次（避免白录十几分钟），`write_baseline` 内部再判一次。
- CLI：`--live` / `--force`；`BaselineExists` 转非零退出 + 明确提示。
- 测试：`server/tests/test_live_record.py` 10 项（注入 4 / 守卫 3 / CLI 2 / 零依赖 1）。

### 阶段二（2026-10-11）—— 已完成

#### gate：先录一条、立刻回放（用户指定的入口）

```
record --case-set v3-gate --baseline-version v3-gate --live   （.tmp 下的单条用例集）
→ 1 条用例，耗时 34.0 s，基线 70,771 B
replay --case-set v3-gate --baseline-version v3-gate
→ exit 0（0.3 s），无 RuntimeError
→ hallucination.total 20 / deterministic_ratio 0.05 / evidence_match_rate 1.0
```

**gate 结论：活库路径的端口调用序列与次数能被纯 FIFO 回放吃下**，没有触发
`regression/ports.py:134-135` 的「已用尽」抛错。据此才敢录满 14 条。

#### 全量录制

```
record --case-set v3 --baseline-version v3 --live --force
→ 20 条用例，耗时 459.3 s（7.65 min）
→ baselines/v3.json：995,752 B（972 KB）

replay --case-set v3 --baseline-version v3 --compare v1   → exit 0
```

| 指标 | v1（替身） | v3（真实） | 差值 |
|---|---|---|---|
| `redflag_intercept_rate` | 1.0 | 1.0 | 0.0 |
| `redflag_false_positive_rate` | 0.0 | 0.0 | 0.0 |
| `diagnosis_drift_rate` | 0.0 | 0.0 | 0.0 |
| `hallucination.total` | 5 | **400** | +395 |
| `hallucination.deterministic_ratio` | 0.0 | **0.11** | +0.11 |
| `latency.llm.p95` | 1 ms | **60,417 ms** | +60,416 |
| `evidence_match_rate` | 1.0 | 1.0 | 0.0 |

注：v3 的 `redflag_intercept_rate = 1.0` 是**真实测量**（6 条红旗用例全部真跑、全部拦截）；
v1 的同名数字是替身自证。两者数值相同、**含义不同**。

#### 体积实测与存储决定（§4.1）

| 分组 | 条数 | 合计 | 均值 |
|---|---|---|---|
| 红旗 | 6 | 20,475 B | 3,412 B |
| 正常 | 14 | 633,487 B | **45,249 B** |
| 合计 | 20 | **995,752 B** | 49,788 B |

最大一条 `llm-bellyache-alias` 63,212 B；最小一条（红旗）3,280 B。

**决定：① 直接进 git。** 理由：972 KB 是一次性快照，仓库现有的 v1 + v2 合计 343 KB，
三份加起来 1.3 MB——对 git 完全可接受，而且 SPEC 3.8 本来就要求用例集与基线
**随版本控制流转**。② 压缩存储会改动基线 schema，破坏「基线是回放唯一事实源」这条性质；
③ 外置则会让 `replay` 依赖仓库之外的文件，与 AC-B-35「回放零外部依赖」相冲突。
**若将来重录后总大小超过 ~5 MB，再回头考虑**（届时优先做的是去掉
`llm_chunks` 与 `frames` 里 content 帧的重复文本，那是最大的一块冗余）。

#### 概念问题 1：v3 的 `drift_rate` 还有意义吗？

**没有 v1/v2 那种「代码改动监测」含义，票面明确写死这一点。** 理由分两层：

1. **同一份 v3 自我回放**：回放是把**录制下来的**图谱响应按 FIFO 喂回去，
   所以候选与基线逐位相同——`drift_rate` 恒为 0，**这是构造使然，不是测量**。
2. **两次 v3 录制之间对比**：候选疾病来自确定性图谱推理（症状固定 → 查询固定 → 结果固定），
   所以**多数情况下可复现**；但任何一条支路在某一次录制里**降级**（网络抖动），
   那一次的候选就会变少，`drift_rate` 会因此上升——于是这个数字把
   「瞬时降级」和「代码改动」混在了一起，**不再能隔离代码改动**。

**它真正有意义的用途**（写进票面）：

- **同一份 v3 反复 replay 的稳定性自检**：确认回放本身是确定性的（期望恒为 0）；
- `replay --compare v1 v3` 的差值说明的是**「替身 → 真实」的差异**，不是漂移，
  也不能当回归判定用。

一句话：**要监测代码改动，仍然用 v1/v2；v3 的漂移率只当回放确定性自检。**

#### 概念问题 2：幻觉率的分母会不会非零？

**会。** 实测（gate 一条 + 全量 20 条）：

- gate 单条：`total = 20`，`deterministic_ratio = 0.05`；
- 全量：`total = 400`，`deterministic_ratio = 0.11`（44 条无据，其中 10 条是本缺陷的假无据）；
- 6 条红旗用例贡献 0（安全门短路、没有回答文本）——与阶段一的预期一致。

所以这条指标在真实回答上**确实工作**：从 1852–3277 字的真实回答里能切出断言、
能匹配到疾病/药品/检查词表与数值。**不存在「指标根本不工作」这个更根本的问题。**

#### 概念问题 3：§3 三处条件标注 + 具体例子

- 三处标注：**本票 §3**（含具体例子）、**`spec.md` §8.3**、**`map.md` 的 v3 语义小节**。
- 具体例子见本票 §3 末尾（`llm-explicit-symptoms` 的「慢性肾炎…依据症状：高血压」整条被判无据）。
