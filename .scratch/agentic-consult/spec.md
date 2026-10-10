# agentic-consult —— 检索增强 · 业务闭环 · 降级容错

**建档**：2026-10-11
**性质**：本目录是「改造计划（2026-10-07 会话压缩版）」的落地规格。范围与决定已拍定，
本文件只固定**范围 / 硬约束 / 偏离纪律 / 验收口径**，供每张票引用，不重复论证方向。
**上游交接**：`%TEMP%\medisentinel-handoff-20261007.md`（信息汇总）、
`%TEMP%\medisentinel-modplan-20261007.md`（计划书）。
**权威**：`SPEC.md` 是唯一权威规格；本文件与其冲突时以 `SPEC.md` 为准，并回来修本文件。

---

## 1. 一句话目标

在 `D:\AILLM\MediSentinel`（FastAPI 异步 + Vue 3 monorepo）上落地四项改造：
**扩知识库 → 混合检索 + 重排 + 评测集 → 业务闭环四段 → 降级容错（超时重试 + 备用模型故障转移）**，
外加（可选、最后）LangChain 换 `LlmPort` adapter。**一票一文件、一票一 commit。**

## 2. 票与执行顺序

编号即执行顺序（`01 → 09`）。每票完成后按仓库惯例做**双轴 review**（Standards + Spec），
结论追加到该票的 `## Comments`。

| 票 | 标题 | 依赖 | 状态 |
|---|---|---|---|
| [01](issues/01-expand-knowledge-base.md) | 扩知识库至 ≥30 chunk（纯数据，地基） | — | ready-for-agent |
| [02](issues/02-hybrid-retrieval-rrf.md) | 混合检索（BM25 + 向量）+ RRF 融合 + 阈值 | 01 | ready-for-agent |
| [03](issues/03-retrieval-quality-eval.md) | 检索质量评测集 + recall@k / MRR | 01 | ready-for-agent |
| [04](issues/04-onnx-rerank.md) | 本地 ONNX 重排（bge-reranker-base） | 02、03 | ready-for-agent |
| [05](issues/05-consult-session-link.md) | 闭环 A：工单关联 AI 会话 | — | ready-for-agent |
| [06](issues/06-doctor-reply-to-record.md) | 闭环 B：医生回复 → 档案沉淀 | 05 | ready-for-agent |
| [07](issues/07-profile-context-prompt.md) | 闭环 C：档案反哺提示词 + 录基线 v2 | 06 | ready-for-agent |
| [08](issues/08-llm-retry-fallback.md) | 降级容错：超时重试 + 备用模型故障转移 | — | ready-for-agent |
| [09](issues/09-langchain-llm-adapter.md) | （可选、最后）LangChain 换 `LlmPort` adapter | 08 | ready-for-agent |

## 3. 已拍定的决定（**不要再讨论方向**）

| # | 决定 | 结论 |
|---|---|---|
| 1 | Docker | **不做**。仓库零 Docker。技能栏 `Docker 基础` 由用户自行删除 |
| 2 | Redis / 消息队列 | **不做**。理由见「已排除项」 |
| 3 | Tool calling | **本月不做**，推到 11 月。它会推翻 AC-B-21 / AC-B-28 / AC-B-35，与「月底出量化数据」冲突 |
| 4 | Q8 重排方案 | **RRF 混合融合 → 本地 ONNX 重排**（`BAAI/bge-reranker-base`），**不动 torch** |
| 5 | Q9 备用模型 | **同一 API key 换模型名** |
| 6 | Q10 顺序 | **先扩知识库，再动闭环** |
| 7 | 闭环反哺实现 | **串行预取传值**（照抄 `history: Sequence[ChatTurn]` 先例），**不新造 `PatientContextPort`** |
| 8 | 执行顺序 | 见上表（01 → 09） |
| 9 | 简历 | **暂不改**。本阶段只做项目，最后一次性出两版成稿（AI 应用版 / 后端版） |

## 4. 硬约束（违反即测试变红，逐条都有断言在盯）

### 4.1 端点门：加一个端点要改 **6 处**

`/api/v1/health` 是唯一例外。任何新端点必须同步：

1. `server/api/v1/<feature>.py` 新 router + `server/api/v1/__init__.py` 导入（`:3-21`）与
   `include_router`（`:24-40`）
2. `SPEC.md` §5.4 端点表 —— `server/tests/test_acceptance_024.py:94-96` 硬断言
   `len(SPEC_5_4) == 78`（**当前 78，加了要改成新值**）
3. `server/tests/test_declared_error_branches.py` 的 `SPEC_ERROR_BRANCHES`
   （key 为**小写 method**）
4. 重导 `contracts/openapi.json`：`cd server; .venv\Scripts\python.exe scripts\export_contract.py`
   （**永不手改**；`test_contract_seam.py:33` 断言与 app 字节相等）
5. `client/tests/contract.test.js:177` 硬编码 `expect(requested).toHaveLength(67)`
6. `client/src/api/client.js` 出口方法

强制断言：`test_acceptance_024.py:124-128` 断言 `SPEC_ERROR_BRANCHES` 覆盖集合 == §5.4；
`:106-111` 断言契约发布集合 == §5.4 ∪ {health}。

### 4.2 `OrchestrationPorts` 是 frozen dataclass 且**字段无默认值**

`server/skills/orchestration/skill.py:89-93`，只有 `graph` / `retrieval` / `llm`。
测试里有 **22 个构造点横跨 14 个文件**（`test_chat_send_api.py:57`、`test_graph_api.py:144,227,256,341`、
`test_safety_gate_short_circuit.py:42`、`test_stream_lifecycle.py:95`、`test_trace_detail.py:157,187` 等，
另有 `adapters.py:31`、`regression/record.py:160`、`regression/replay.py:67`）。
→ **新增字段必须给默认值**，否则 22 处 `TypeError`。

### 4.3 `asyncio.gather` 结果**按位置读**

`server/skills/orchestration/skill.py:243-254` 先入队 retrieval（`:244-246`），条件追加 graph（`:248-253`），
结果在 `:256-259` 用 `outcomes[0]` / `outcomes[1]` 读。
→ **不要在 gather 里追加并行支路**（会索引错位）。档案反哺走**串行预取**。

### 4.4 回归回放是**纯 FIFO 游标，且只录三个方法**

`server/regression/ports.py`（186 行）：

- 只录 `infer_diseases`（`:71-76`）、`retrieval.search`（`:104-106`）、`llm` 的 chunk 列表（`:117-121`）
- 回放侧 `_queue[_cursor]; _cursor += 1`，**从不匹配参数**（模块 docstring `:5` 的「(method, args) -> result」言过其实）
- 调用未录制的方法 → `RuntimeError("回放不访问图库读取接口")`（`:140-153`）；调用次数超额 →
  `RuntimeError(…已用尽…)`（`:134-135`）
- **`regression/ports.py` 不得 import `adapters` / `neo4j` / `chroma`**（docstring 承诺 + AST 测试
  `server/tests/test_regression_record_replay.py:169-179`）

→ **任何新端口/新数据源都必须同时进：录制侧、回放侧、`baseline` 的 `ports` 键、`tests/doubles.py` 替身**，
否则 AC-B-35「回放零外部依赖」直接红。**首选做法是不新增端口**：把新能力放进既有端口的实现层内部，
让编排层的调用序列保持不变。

### 4.5 「生成不可降级」是写死的原则

`SPEC.md:398` 原文：向量检索与图谱推理属增强支路，不可用**不产生错误码**，标 `degraded` 继续；
**大模型生成不可用无法降级**，返回 503 / 504。
代码三处重申：`server/skills/ports.py:35`（"The one port generation cannot degrade on"）、
`skill.py:12-13`、`skill.py:60`。

→ **备用模型切换必须重新表述为「故障转移（切换执行单元，生成能力不降级）」，并改 `SPEC.md:398`**，
否则会被判为回归。

### 4.6 其他纪律

- **每票必须登记 divergence**（追加到 `.scratch/medisentinel/intentional-divergences.md`，标 scope）。
- ⚠️ **已核实的耦合（已拍板修法）**：`server/regression/divergences.py:19` 的正则是
  `^(A|H)-\d+$` —— 新增家族（`S-*`）的条目会被**静默忽略**。修法：
  1. 正则扩成 `^(A|H|S)-\d+$`；
  2. **族 ↔ scope 一一对应**：`A-*` = `ai-chain`、`H-*` = `http-contract`、
     `S-*` = **新增独立 scope `stack`**；
  3. 新增访问器 `stack_ids()`（与 `ai_chain_ids()` / `http_contract_ids()` 并列）。
  **`stack` 条目不进任何豁免集、也不进 024 的消费集**——它只做可追溯登记。
  把框架级变更塞进 `ai-chain` 会扩大漂移/幻觉豁免分母，让门禁对本次改动失明，**禁止**。
- ⚠️ **连带会变红的硬编码断言**（新增条目时必须同步，不能只改实现）：
  - `server/tests/test_regression_divergences.py:21` ——
    `ai_chain_ids(registry) == [A-1…A-7]`，新增 `ai-chain` 条目即红；
  - `server/tests/test_acceptance_024.py:155` ——
    `http_contract_ids(...) == [H-1…H-12]`，新增 `http-contract` 条目即红；
  - `server/tests/test_regression_divergences.py:27-28` 读的是**已冻结的 v1 基线**里的列表，
    只增登记册、不改 v1 时仍绿；重录基线时一并复核。
- commit 前缀沿用 `[TICKET-0NN] …`；**新 slug 的编号会与既有 `TICKET-001…030` 撞号**，
  采用哪种编号见「未决项」。
- 每票自跑**双端测试**并贴结果：
  - 后端 `cd server; .venv\Scripts\python.exe -m pytest -q --basetemp=.tmp\pytest`
  - 前端 `cd client; npm test`
- `SKILL.md` 的四节必须与实现保持一致（有「文档与运行时一致」类测试的传统）。

## 5. 有意偏离登记（divergence）

本次四处框架级变更与新增端点都属有意偏离，逐条追加到
`.scratch/medisentinel/intentional-divergences.md` 并标 scope。**族 ↔ scope 一一对应**：

| 族 | scope | 谁消费 |
|---|---|---|
| `A-*` | `ai-chain` | TICKET-023 豁免漂移 / 幻觉分母 |
| `H-*` | `http-contract` | TICKET-023 只记录，TICKET-024 消费 |
| `S-*` | `stack` | **只有 `stack_ids()` 读，不进任何豁免集** |

逐票落点（编号在票内确定；**新增条目的同一票必须同步改对应硬编码断言**）：

- 票 02 混合检索（RRF 融合）→ `S-1` / `stack`
- 票 04 本地 ONNX 重排 → `S-2` / `stack`
- 票 05 工单↔会话新端点 → `H-13` / `http-contract`
- 票 06 档案来源与撤回新端点 → `H-14` / `http-contract`
- 票 07 档案反哺 → **拆两半**：机制（提示词装配新增档案段）→ `S-3` / `stack`；
  行为（是否进问诊回放口径）→ `A-8` / `ai-chain`
- 票 08 生成故障转移（改 `SPEC.md:398` 措辞）→ `S-4` / `stack`

**票 02 的第一件事**是把 `regression/divergences.py` 扩成正则 + `stack` scope + `stack_ids()`
（见 4.6），否则后面所有 `S-*` 登记都是空转。

## 6. 已排除项（**不要重新提议**）

| 排除 | 理由（实测） |
|---|---|
| Docker | 用户明确排除；仓库零 Docker |
| Redis 缓存 | 6379 无服务；Chroma 与本机同机，缓存省的是个位数毫秒；且缓存 `/chat/send` 生成结果会破坏安全门短路语义与医疗数据隔离 |
| 消息队列 | 已有等价物：`KnowledgeJobs.schedule_vectorize` → `asyncio.create_task`（`server/services/knowledge.py:53-59`）+ `vector_status` 0/1/2/3 状态机 + 前端 3 秒轮询 + 失败置 3。换 Celery/arq 是重写已有能力 |
| Tool calling | 本月不做（推翻 3 条验收标准 + 会让量化数据作废一次） |
| 「本地向量库兜底」 | 语义不成立（向量库是上下文支路，不是生成的替代；生成失败仍只能 503/504），且冲突 `SPEC.md:398` |

## 7. 已决项（2026-10-11 用户拍板）

| # | 问题 | 结论 |
|---|---|---|
| 1 | divergence 新族编号 | 用 `S-*`，**独立 scope `stack`** + 独立访问器 `stack_ids()`；不塞进 `ai-chain`（会扩大豁免集、让门禁对本次改动失明）。同改 `regression/divergences.py` 正则、`test_regression_divergences.py:21`、`test_acceptance_024.py:155` 三处。票 07 的 prompt 改动拆两半登记（机制 `S-*`/`stack`、行为按回放口径定 `ai-chain`） |
| 2 | 票 05 新端点归属校验理由 | 采纳：角色与越权面不同——医生读的是被指派/待认领工单的会话，**工单本身即授权凭证**；已认领工单只有负责医生可见 |
| 3 | 评测集标注口径 | 采纳：二值相关（命中标注文件即相关）、20–30 条、单 query 可标多文件。**标注集必须在跑指标之前定稿，不允许事后回溯调整真值** |
| 4 | 档案反哺开关与配额 | 采纳：本阶段**不做开关**；取过敏史 + 最近 **3** 条档案，合计 **≤ 600 字** |
| 5 | `_record` 的 `"cancelled"` 死代码 | 采纳：顺手修——`server/skills/protocol.py:66` 的 `except Exception` 捕不到 `CancelledError`，补 `BaseException` 分支并写 `cancelled` span（落点见票 02「顺带修」） |
| 6 | `Docker 基础` 从简历技能栏删除 | 同意：**本阶段不动简历** |

## 8. 验收与命令

| 用途 | 命令（`server\` 下运行 Python，`.env` 是相对路径） |
|---|---|
| 后端测试 | `cd server; .venv\Scripts\python.exe -m pytest -q --basetemp=.tmp\pytest` |
| 前端测试 | `cd client; npm test` |
| 契约导出 | `cd server; .venv\Scripts\python.exe scripts\export_contract.py` |
| 回归录制/回放 | `cd server; .venv\Scripts\python.exe scripts\regression.py record\|replay --case-set v1 --baseline-version v1` |
| 知识库灌数 | `cd server; .venv\Scripts\python.exe scripts\init_knowledge.py` |

## 变更记录

- 2026-10-11：建档。落 9 张票（01–08 必做、09 可选）、九项已定决定、6 条硬约束、
  排除项与 6 条未决项。核实 `regression/divergences.py` 正则只认 `A-*`/`H-*`（4.6）。
- 2026-10-11：用户拍板 §7 六条。`S-*` 定为独立 scope `stack` + `stack_ids()`；
  落「族 ↔ scope 一一对应」映射与三处硬编码断言的同步义务（4.6 / §5）；
  票 07 登记拆两半；补「评测集先定稿、不得回溯改真值」与「取消分支 span 缺口顺手修」。
