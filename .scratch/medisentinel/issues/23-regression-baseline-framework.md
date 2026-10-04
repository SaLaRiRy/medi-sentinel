# 23: 回归基线框架

**What to build:** 让行为变化可度量：一条命令录制基线，一条命令回放对比；回放时不触碰图库、向量索引、嵌入服务与大模型，输出红旗拦截率、误拦率、诊断漂移率、幻觉率与按路径分组的 P95 延迟。

**Blocked by:** 07（orchestration 正常路径）、08（安全门短路）、09（降级不阻断）

**Status:** ready-for-agent

- [ ] 一条命令录制基线，产出包含输入集、各 Skill 输出、最终结果与耗时的版本化基线
- [ ] 一条命令回放对比；回放期间图库、向量索引、嵌入服务与大模型的调用次数均为 0
- [ ] 回放输出 `MetricsReport`，含红旗拦截率、误拦率、诊断漂移率、幻觉率与 P95 延迟
- [ ] 幻觉率同时给出 `deterministic_ratio`、`judged_ratio` 与 `total`
- [ ] P95 延迟按 `intercepted`、`llm`、`degraded` 三条路径分组输出，不合并
- [ ] 同一基线与同一代码重复回放两次，指标完全一致
- [ ] 代码未变更时诊断漂移率为 0
- [ ] 基线用例集版本化，随基线一同纳入版本控制

## Design（定稿 — 已确认，冻结）

> 本票第一件产出（2026-10-04 冻结）。实现以本段为准；每条给「选择 + 理由」。

### 1. case set 与基线放哪 → `server/regression/`（框架 + 数据），测试在 `server/tests/`

```
server/regression/
├── schema.py     # case / baseline 的 pydantic 模型
├── record.py     # 录制
├── replay.py     # 回放 + 指标计算（B-1 驱动）
├── metrics.py    # MetricsReport 与四项指标定义
├── ports.py      # RecordingPort / ReplayPort / judge seam
├── cases/v1.json
└── baselines/v1.json
```

理由：仓库把「能力」放包（`skills/`、`services/`），`tests/` 只放 pytest 模块与 doubles；
case set / 基线是**版本控制的数据**（SPEC §3.8「随基线一同纳入版本控制」），不是 pytest
夹具，放 `tests/` 既破坏分层又会被 pytest 误收集。B-1 把回放定为「唯一驱动点」，它是服务端
一等能力，应可被操作命令导入而不依赖 pytest。

### 2. 命令面 → `server/scripts/regression.py record | replay`

```
python scripts/regression.py record --case-set v1 --baseline-version v1
python scripts/regression.py replay --case-set v1 --baseline-version v1 [--report out.json]
```

`record` 写 `regression/baselines/<version>.json`；`replay` 打印 `MetricsReport` JSON，遇
阻断性失败（拦截率 < 100% 或误拦率 > 0%）非零退出。`--cases-dir/--baselines-dir` 可覆盖，
便于测试不碰已提交文件。

理由：仓库的操作命令都是 `python scripts/<name>.py`（`export_contract`、`init_graph`、
`init_knowledge`），README 也在此登记；一对 record/replay 同放一个脚本的两个子命令最省。
脚本只做 argparse 薄壳，真正的 API 是可测的包函数。备选 `python -m regression record`
仅为不破坏既有 `scripts/` 约定而放弃。

### 3. B-3 recorded responses + B-4 trace evidence 怎么接

- **record**：用 `RecordingPorts` 装饰器包住 B-3 三端口，逐次捕获
  `(method, args) → result` 与 LLM chunk 序列；B-4 sink（`TraceRepository` 或
  `InMemoryTraceSink`）捕获 span 与 route。每条 case 落库：输入、`route{skills_run,
  skills_skipped}`、`ports{graph, retrieval}`、`llm.chunks`、全部 SSE 帧、各 Skill 输出、
  `spans`（B-4 证据）、`duration_ms`、标签（`red_flag`）。
- **replay**：由基线重建 `OrchestrationPorts`（`ReplayGraphPort`/`ReplayRetrievalPort`/
  `ReplayLlmPort` 按录制顺序作答），再跑 B-1 得到同样的帧，全程零外部 I/O；对比时**丢弃
  随机 `trace_id`**（它是身份不是行为），其余全比。
- **「调用计数为 0」**（AC-B-35）：把真实适配器槽位接成计数守卫端口并断言 0 次调用；
  同时 `regression/ports.py` 不 import `adapters`/`neo4j`/`chroma`。
- **B-4 证据**：基线的 `spans`+`route` 是回放证据源；回放断言 route 决策与 span 名/状态
  一致，`degraded` 路径分组由 `skills/trace.py:degraded_branches` 读出。

理由：SPEC §4.4 已把 B-1 定为唯一驱动点、B-3 定为可复现性来源、B-4 定为证据来源。

### 4. 幻觉判定层的注入 seam

- 新增 `JudgePort` Protocol：`async judge(assertion, context) -> bool`；真实实现
  `LlmJudgePort(llm: LlmPort)`，**默认接 `UnavailableLlmPort`**（应用默认），judge 可注入 stub。
- `hallucination = {deterministic_ratio, judged_ratio, total}`：确定性层用仓库内图谱词表
  （`graph/ontology.py` 的 `_NODES_BY_LABEL`：数值/药品/疾病/检查名）+ 回放检索上下文做字面
  匹配；判定层用 `JudgePort` 判剩余自由文本。
- judge 不可用时**降级不报错**：`judged_ratio = 0.0`，报告加 `judge_available: false`
  （附加字段）以免被误读成「无幻觉」；`total` 计已评估断言数。
- 注入点：`regression.metrics.hallucination(answer, context, judge=...)` 与 CLI `--judge`；测试传确定性 stub。

理由：SPEC §3.8 强制三项都要给出；应用默认无大模型，judge 必须可注入且缺失时按
「降级不阻断」处理，而不是让整次回放失败。

### 5. 20 条 case 构成与录制时机

选择：**现在写死 `cases/v1.json`（20 条），现在录 `baselines/v1.json`**；扩容只加 `v2`，
基线不可变（SPEC：版本化）。

| 组 | 条数 | 内容 | 期望 |
|---|---|---|---|
| 红旗 | 6 | 安全门各红旗族（胸痛+出冷汗+呼吸困难、大出血、意识障碍、剧烈头痛+呕吐、高热+皮疹、抽搐） | `decision=intercept` |
| 正常（llm） | 8 | 口语别名（头疼/肚子痛/拉肚子/嗓子痛，AC-B-19）、显式症状、多症状（AC-E-01）、否定式（AC-E-03，AC-B-12） | `safety` 帧不出现 |
| 降级 | 4 | 图库不可用 ×2 / 向量不可用 ×2（含 AC-E-04） | `done.degraded` 非空 |
| 边界 | 2 | 归一化空 → `graph-inference` 跳过（AC-B-23）；纯否定句 | route 含跳过理由 |

理由：AC-B-34 要求版本化 case set + 基线入库；AC-B-39/40（可复现、漂移 0）只有在基线已提交
时才可断言。仓库 LLM 默认 `UnavailableLlmPort`，故 `record` 用**确定性录制端口**（脚本化
LLM + 仓库内图/向量假实现）离线录；真适配器落地后再以它录 `v2`。绝不改 `v1`。

**P95 分组（对照 SPEC §3.8 原文的结论）→ 取 exclusive（互斥），优先级
`intercepted` → `degraded` → `llm`，每条 case 只计一次。**

原文两处：

- §3.8 指标表：「P95 延迟 | 端到端耗时 95 分位，按路径分组统计：`intercepted`（被拦截）、
  `llm`（走完大模型）、`degraded`（含降级支路） | 分组报告，不合并」
- AC-B-38：「P95 延迟按 `intercepted`、`llm`、`degraded` **三条路径**分组输出，不合并」

结论：括号是**性质描述**（「含降级支路」在性质上可与「走完大模型」重叠），但原文并
**未明确**说三组重叠，且 AC-B-38 写「**三条路径**」——路径一词倾向"每条 case 走一条"。
按你的规则（"若括号明确读成重叠才以 SPEC 为准"），此处**不构成明确重叠**，故保留互斥。
优先级取 `degraded` 高于 `llm`：degraded 是更具体、更需要被看见的路径。若日后 SPEC
修订为明确重叠，则改回"llm 与 degraded 可同时计数"。

### 6. `/regression/*` 三端点（决策 (a)：本票落地）

三个端点（角色均为 `admin`，SPEC §5.4）：`POST /regression/runs` → `{run_id}`；
`GET /regression/runs/{run_id}` → `{status, metrics}`；`GET /regression/baselines` →
`BaselineView[]`（可用基线版本清单）。

**同步 vs 异步 → 异步 job。** 首要理由来自契约形状本身：`POST` 只回 `{run_id: str}`，而
`GET` 回 `{status, metrics: MetricsReport|null}` —— 有独立 `status` 且 `metrics` 可为 null，
说明「提交-轮询」是 SPEC §5.3/§5.4 定死的模型，不是可选项。次要：回放是长任务，同步 handler
会把整个回放按在请求路径上（SPEC §3.1 禁止请求路径阻塞、「每请求一个异步会话」）。
实现：仿 `services/knowledge.py:KnowledgeJobs` 的进程内 job 注册表（`regression/runs.py`，
后台任务 + 按 `run_id` 记 `status`/`metrics`），在 `main.py` 挂到 `app.state`。
`status` 取值：`pending | running | succeeded | failed`。

错误分支（照 SPEC §5.4 原文）：POST `{401,403,404,422}`（404 = case set 或 baseline
版本不存在）；GET run `{401,403,404}`（404 = run_id 不存在）；GET baselines `{401,403}`。
三条一并进 `tests/test_declared_error_branches.py`，补全 §5.4 覆盖。契约由
`scripts/export_contract.py` 重新生成（不手改），`sse-events.json` 不动。

### 7. replay 的 LLM 模式与两条工作流

- **默认（Skill 变更工作流）**：`replay` 用 `ReplayLlmPort` 重放录制 chunks，**LLM 恒定
  不变**，让 Skill / 编排的改动显影；行为指标差异可归因到 Skill。这是 AC-B-39/40 的常规路径。
- **换模型工作流**：`record` 用新模型 / 新适配器录 `v2`（`v1` 不动），再
  `replay --baseline-version v2 --compare v1`，打印两份 `MetricsReport` 与差值
  （漂移率 / 幻觉率 / P95 趋势）。SPEC 落点：§1.3「修改提示词、扩充词典、调整排序、
  升级模型之后…漂移有多大 / 延迟变差了多少」与 §3.8 指标表的「趋势不得无故上升」；G5 亦
  要求框架同时支持录制与回放对比。
- **文字校正**：SPEC 里**没有**「换模型后自动对比」这句原文，最接近的是 §1.3 与 §3.8 的
  「趋势不得无故上升」。且 SPEC §7.9 把「大模型与嵌入模型的选型对比、切换与灰度」列为
  **范围外**——故本工作流是**框架的使用方式**（使两次基线可比），不是 023 去替模型做选型。

### 8. baseline 比较的 drop / normalize 规则（显式清单）

对比前必须剔除"每次运行必然不同"的字段，否则框架刚建好就恒红。

**DROP（身份 / 墙钟，永不比较）**

- `trace_id`：`trace` 帧、`done.trace_id`、`error.trace_id`、span.trace_id、route.trace_id
  （每次 `uuid4`）。
- 时间戳：span.`started_at`、route.`decided_at`、一切 `create_time` / `update_time`。
- 耗时：帧 `done.cost_time`、span.`duration_ms`、replay 自身墙钟 `measured_ms`。

**NORMALIZE（比较前规范化）**

- `session_id`：每条 case 在 case set 里固定（录制与回放同一值）。
- 浮点 `coverage`：`round(x, 2)`（SPEC §3.6 的 2 位小数口径）。
- JSON：按解析后的对象比较、忽略键序；数组顺序**保留**（候选疾病 / 引用顺序本身是行为，
  漂移率按**有序列表**比）。
- `degraded` 列表：按固定顺序（retrieval → graph）比较。

**确定性（AC-B-39 的关键取舍）**

- `MetricsReport.latency` **不由 replay 墙钟重算**，而取 baseline 里录制的每条 case
  `duration_ms`（baseline 每条 case 记 `path` 与录制 `duration_ms`）。这样两次回放的四项
  指标**完全一致**（AC-B-39）；换模型工作流中 v2 的录制耗时自然反映新模型的延迟差异。
- 行为指标（拦截率 / 误拦率 / 漂移率 / 幻觉率）由本次回放重新计算；相同代码 + 相同基线
  ⇒ AC-B-40 漂移 0。
- **代价（已确认接受）**：Skill 变更工作流里 P95 是录制时的延迟快照，不反映本次回放墙钟。
- **这不是缺陷（必读，避免后人误读成 bug）**：
  - AC-B-39「四项指标完全一致」正是**由「latency 取 baseline 录制值」满足的**；
    行为指标照常由本次回放重算（同代码 + 同基线 ⇒ AC-B-40 漂移 0）。
  - **延迟漂移的观察方式是「两次录制值对比」（v1 vs v2）**，不是 replay 墙钟。
  - replay 墙钟在 CI 上**不可复现**（负载抖动、调度），不适合做基线；把它放进指标只会
    制造假回归。因此 replay 时 P95 不随本次墙钟变化是**刻意设计**，不是 bug。
