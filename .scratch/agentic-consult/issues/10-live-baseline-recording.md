# 10: 活库重录回归基线（只录数据）

**What to build:** `scripts/regression.py record` 增加 `--live` 路径：**从 scripts 侧注入真实
B-3 适配器**（`adapters.build_graph_store` / `build_vector_store` / `build_llm`），把一次真实
问诊（Neo4j 图谱 + 活库向量检索 + 真实模型）录成**新版本基线 v3**。这样
「红旗拦截率 / 误拦率」第一次由**真实测量**给出，而不是 `Fixture*` 替身的自证。

**只录数据**：不改判定层、不改编排、不改既有 v1 / v2。

**Blocked by:** 无（依赖 MySQL / Neo4j / 真实 API key 三样在线）

**Status:** needs-triage —— 用户复核票面后置 `ready-for-agent`

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
- [ ] 6 条全部走 `intercept` 路径：`route.skills_run == ["safety-gate"]`、
      有 `safety` 帧、无 `content` 帧、`done.references == []`、`done.graph == []`。
- [ ] 回放这段基线：`redflag_intercept_rate == 1.0`、`redflag_false_positive_rate == 0.0`、
      `evidence_match_rate == 1.0`，且数字来自**真实录制**（帧带真实 `trace_id`、
      span 时间戳非零）。
- [ ] 记录 `baselines/v3.json` 这一阶段的实际体积（应与 v1 的 6 条同量级）。
- [ ] 票面 Comments 写明：这一阶段**没有 LLM chunk、没有检索/图谱调用**
      （红旗短路本来就是 0 次），所以体积与耗时都不构成问题。

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

（待开工后记录：阶段一实测、阶段二实测、体积决定、三处条件标注的落点。）
