# SPEC —— AI 智能医疗问诊平台（异步 · Skill 化重建）

> **本规格的性质**：这是一个**新项目**的规格，不是对现有工程的改造建议。功能范围以 `FUNCTIONAL_SPEC.md` 为基线并保持对等，架构、并发模型与 AI 链路组织方式整体重写。
> **领域词汇**：沿用 `FUNCTIONAL_SPEC.md` 附录 A 的术语表。本规格引入的新术语在首次出现处定义。
> **阅读顺序**：第 1 章问题 → 第 2 章目标 → 第 3 章约束 → **第 4 章 seam（实现从哪里切开）** → 第 5 章接口契约 → 第 6 章验收标准 → 第 7 章不做什么。

---

## 1. Problem

### 1.1 AI 链路是一个不可分割的黑盒

现有实现中，一次问诊的完整推理被压缩在单个服务类的两个方法里：`_build_context` 同时完成向量检索、症状提取、图谱推理与上下文拼接；`chat_stream` 同时完成提示词组装、模型调用与事件产出。其直接后果：

- **任一环节都无法单独测试。** 想验证「症状归一化是否正确」必须启动图数据库、向量索引、嵌入服务和大模型，或对整个方法做整体 Mock。
- **任一环节都无法单独替换。** 更换症状词典、调整图谱排序、切换嵌入模型、更换提示词，都只能改动同一个方法体的内部，改动的影响范围无法界定。
- **无法回答「哪一步错了」。** 回答质量下降时，无法区分是归一化漏词、图谱排序失准、检索召回不足，还是模型自由发挥。

### 1.2 症状词汇存在两张割裂的词表，口语输入大面积失效

症状提取使用一张 30 词的硬编码列表，别名归一化使用另一张 22 条的映射表，且两张表分处不同模块。两表交集只有一个词，导致 22 条别名中有 21 条在实际对话链路中**永远无法被触发**。用户用口语说「头疼」「肚子痛」「拉肚子」时，系统不会识别为任何症状，也就不会触发任何图谱推理 —— 而这恰恰是普通患者最自然的表达方式。

### 1.3 没有任何流程级的安全拦截

系统提示词里有 4 条安全约束，但它们的作用方式是「请求大模型自觉遵守」。这意味着：

- 无论用户输入什么 —— 包括「胸痛伴大汗、濒死感」「意识丧失」「呕血」「自杀观念」 —— 系统都会走完检索、组装上下文并调用大模型。
- 安全提示的产生取决于模型的服从程度，而非流程的确定性保证。提示词被改写、模型被更换、上下文过长挤掉系统提示，都会让这层保护失效或漂移。
- 没有任何机制能回答「今天有多少条急症输入被正确拦截」，因为不存在「拦截」这个事件。

### 1.4 没有可观测性，没有回归基线

现状的可观测性只有写向控制台的文本日志，没有 trace_id，没有结构化字段，无法按请求检索、无法按环节聚合、无法回放。其直接后果是：**任何行为改动都无法被度量**。修改提示词、扩充词典、调整排序、升级模型之后，没有人能回答「诊断结果的漂移有多大」「幻觉变多了还是变少了」「哪些之前被识别出的症状现在识别不出来了」「延迟变差了多少」。改动只能靠人工抽查和主观感觉来判断，回归风险不可见。

### 1.5 请求路径是同步阻塞的

数据库会话、图数据库驱动与嵌入调用均为同步阻塞式，只有大模型调用使用了异步流式接口。一次问诊会在等待图数据库往返、等待嵌入服务响应、等待模型首字的过程中占用工作线程。并发用户数上升时，吞吐下降的原因是线程被 I/O 等待占住，而不是资源真的不足。

### 1.6 前后端契约是隐含的

73 个端点的请求体、响应体、错误语义只存在于两侧的实现代码里。响应外壳规定业务失败时 HTTP 状态仍为 200，成败必须靠解析响应体里的 `code` 判断；大模型驱动的流式接口更是只有一份「帧长什么样」的默契，没有独立可校验的协议定义。任何一侧的改动都可能静默破坏另一侧。

### 1.7 对当事人的实际影响

| 角色 | 现状下的处境 |
|---|---|
| 患者 | 口语化描述症状得不到任何图谱辅助；急症输入不会被流程拦截，能否收到「立即就医」的建议取决于模型的服从程度 |
| 医生 | 无法判断 AI 给出的候选疾病依据了哪些症状、哪些知识片段 |
| 开发者 | 改动 AI 链路的任何一环都无法局部验证，只能在整体上「跑一遍看看」 |
| 运维与质量 | 无法定位线上回答质量变化的环节，无法用数据回答「这次改动是变好还是变差」 |

---

## 2. Goal

### 2.1 一句话目标

在保留 `FUNCTIONAL_SPEC.md` 功能对等的前提下，把 AI 问诊链路重建为**五个边界清晰、契约明确、可独立测试的 Skill**，在其最前端加上一道**确定性的、先于大模型调用的红旗安全门**，并让**每一次 Skill 调用与大模型调用都留下可回放的结构化痕迹**，使行为变化从「靠感觉」变为「可度量」。

### 2.2 具体目标

| # | 目标 | 可度量的完成标志 |
|---|---|---|
| G1 | **Skill 化**：症状归一化、图谱推理、向量检索、安全约束、编排各为独立 Skill，各自拥有 `SKILL.md` | 5 份 `SKILL.md` 存在，每份含输入输出 Schema、触发条件、边界情况、测试用例四节；每个 Skill 可在不启动外部依赖的情况下被单独测试 |
| G2 | **安全前置且短路**：安全约束是独立的 Process Rules Skill，红旗检测先于大模型调用；命中即返回安全提示，不调用大模型 | 红旗用例下大模型端口调用次数为 0，且归一化、检索、图谱端口调用次数均为 0 |
| G3 | **词汇统一**：归一化使用**唯一一份**症状词表（标准词 + 别名 + 否定式规则） | 别名映射在对话链路与症状推理链路**同样完整生效**；不存在第二份提取词表 |
| G4 | **全链路可观测**：每次 Skill 调用与大模型调用产出结构化 trace | 每条 trace 含 trace_id、Skill 名、耗时、输入摘要、输出摘要、路由决策；可按 trace_id 与时间范围检索 |
| G5 | **回归基线从第一天就在**：支持录制基线与回放对比 | 一条命令录制基线、一条命令回放对比；输出红旗拦截率、诊断漂移率、幻觉率、P95 延迟四项指标 |
| G6 | **全异步**：请求路径无同步阻塞调用 | 全链路异步；并发 N 个问诊请求时事件循环不被阻塞（以并发测试与阻塞调用检测验证） |
| G7 | **契约显式**：所有前后端交互有独立契约 seam | 方法、路径、请求 Schema、响应 Schema、错误码、SSE 事件 Schema 全部显式定义；两侧测试均针对同一份契约校验 |
| G8 | **功能对等**：既有业务域行为保持不变（除第 3.6 节明确列出的变更项） | `FUNCTIONAL_SPEC.md` 描述的业务规则在新项目中逐条通过回归验证 |

### 2.3 目标状态下的单次问诊

```
用户输入
   │
   ▼
[编排 Skill] 生成 trace_id，开始记录
   │
   ├─▶ ① 安全约束 Skill（Process Rules，确定性）  ← 最先执行
   │        │
   │        ├── intercept ──▶ 直接产出安全提示并结束
   │        │                 （不执行 ② ③ ④，不调用大模型）
   │        │
   │        └── allow ──┐
   │                    ▼
   ├─▶ ② 症状归一化 Skill（确定性，唯一词表）
   │        │
   │        ▼
   ├─▶ ③ 并行双支路（互不依赖、互不筛选）
   │        ├── 向量检索 Skill ──▶ 知识片段 + 引用
   │        └── 图谱推理 Skill ──▶ 候选疾病（覆盖率排序）
   │                    │
   │                    ▼
   ├─▶ ④ 上下文组装（确定性）
   │        │
   │        ▼
   └─▶ ⑤ 大模型流式生成 ──▶ SSE 事件流
                │
                ▼
        trace 落库，可回放
```

---

## 3. Constraints

### 3.1 后端技术栈

| 项 | 约束 |
|---|---|
| 数据访问 | SQLAlchemy 2.0 **异步**：`AsyncSession`、`async_sessionmaker`、`select()` 风格查询构造 |
| Web 框架 | FastAPI **异步**：路由处理函数为 `async def`；请求路径内不得出现同步阻塞调用 |
| 图数据库 | Neo4j **异步驱动**（`AsyncGraphDatabase` 异步会话） |
| 大模型与嵌入 | LangChain **异步调用**（异步流式接口、异步嵌入接口） |
| 依赖注入 | 每请求一个 `AsyncSession`，请求结束回滚或提交并归还连接池 |

**禁止**：在请求路径中使用同步数据库会话、同步图数据库会话、同步 HTTP 客户端。允许的例外只有纯 CPU 的短计算（词表匹配、字符串处理、排序），且不得包含 I/O。

### 3.2 前端技术栈

| 项 | 约束 |
|---|---|
| 框架 | Vue 3 |
| 构建 | Vite |
| 路由 | Vue Router |
| 状态 | Pinia |
| 通信 | 仅 RESTful API（含 SSE 流式端点） |

**前端是独立层**：不得直连关系型数据库，不得直连图数据库，不得直连向量索引，不得持有任何后端连接串或密钥。前端只负责三件事：视图渲染、用户交互、API 调用。

### 3.3 架构约束

| 项 | 约束 |
|---|---|
| 分层 | 前后端分离 |
| 仓库结构 | Monorepo，`client/` 与 `server/` 两个顶层目录 |
| 职责边界 | 前端：视图渲染 / 用户交互 / API 调用。后端：AI 链路 / 图谱查询 / RAG 检索 / 全部业务规则 |
| 业务规则位置 | 所有校验、状态语义、权限判定、级联规则均在后端，前端不得复制业务规则作为唯一依据 |

### 3.4 Skill 化约束

五个 Skill，各一份 `SKILL.md`：

| Skill 名 | 类别 | 是否含大模型调用 |
|---|---|---|
| `safety-gate` 安全约束 | **Process Rules Skill** | 否 |
| `symptom-normalization` 症状归一化 | 确定性能力 Skill | 否 |
| `vector-retrieval` 向量检索 | 确定性能力 Skill | 否（嵌入模型调用不算大模型生成调用） |
| `graph-inference` 图谱推理 | 确定性能力 Skill | 否 |
| `orchestration` 编排 | 编排 Skill（Agent 本体） | **是，且仅此一个** |

**每份 `SKILL.md` 必须包含以下四节**，缺一不可，且四节内容必须与运行时行为一致：

1. **输入输出 Schema** —— 可机器校验的字段名、类型、必填性、约束、示例。
2. **触发条件** —— 何时被调用、何时被跳过、被跳过时向 trace 写入什么理由。
3. **边界情况** —— 空输入、超限输入、外部依赖不可用、语义歧义（否定、引述、多命中）等，以及每种情况的确定性处置。
4. **测试用例** —— 至少包含正例、负例、边界例；每条用例给出输入与期望输出，可直接转为可执行测试。

**Skill 的运行语义（本规格的关键定义）**：Skill 是**后端确定性运行时组件**，通过统一的 `invoke(input) → output` 协议被调用，输入输出均按 `SKILL.md` 声明的 Schema 校验。除 `orchestration` 外，任何 Skill **不得**调用大模型。`SKILL.md` 是该组件契约的权威文档，不是给大模型阅读的提示词。

### 3.5 安全约束

| 项 | 约束 |
|---|---|
| 形态 | 安全约束必须是**独立的 Process Rules Skill**，不与其他 Skill 合并 |
| 时序 | 红旗症状检测在**大模型调用之前**执行，且是编排的第一顺位 |
| 命中行为 | 检测到红旗症状时**直接返回安全提示，不调用大模型** |
| 短路范围 | 命中红旗时**全链路短路**：归一化、向量检索、图谱推理、大模型生成均不执行 |
| 确定性 | 检测为确定性规则匹配，不依赖大模型判断；结果可复现 |
| 可审计 | 命中时 trace 必须记录命中的红旗标识、匹配到的原文片段、依据的规则版本 |

### 3.6 与 `FUNCTIONAL_SPEC.md` 的行为差异（必须逐条落入回归基线）

**保留**（必须逐条通过回归验证）：

- 14 个实体的字段语义、唯一性约束与关系基数
- 三角色模型（`user` / `doctor` / `admin`）与令牌语义
- 全部状态值与语义（预约 0–3、工单 0–1、向量化 0–3、通用 0/1）
- 级联删除的范围与顺序
- 科室删除保护（有医生则拒绝）
- 健康档案的归属校验
- 主诉的前后端编码约定（`标题：正文`，全角冒号）
- 会话标题生成规则（前 20 字符 + 省略号）、消息计数 +2、历史取最近 6 条
- 分页响应外壳、时间格式、角色展示映射

**架构性变更**（行为等价，实现不同）：

| 变更 | 说明 |
|---|---|
| 同步 → 异步 | 全部 I/O 改为异步；对外行为不变 |
| 单方法 RAG → 五 Skill | 推理过程被切开；最终上下文与输出的**内容规则**不变 |
| 控制台日志 → 结构化 trace | 日志仍在，但权威记录是可回放的 trace |
| 业务失败的表达 | 不再使用「HTTP 200 + `code: 400`」；错误码统一承载在真实 HTTP 状态码上，响应体 `code` 与之保持一致 |

**有意修复**（新行为，需在回归基线中标注为已变更）：

| 修复 | 原状 | 新行为 |
|---|---|---|
| 症状词表统一 | 提取表 30 词与别名表 22 条割裂，21 条别名在对话链路不可达 | 唯一一份词表；22 条别名在对话链路与症状推理链路**同等生效** |
| `probability` 更名 | 字段名为 `probability`，实际语义是覆盖率 | 更名为 `coverage`，仍为「命中数 ÷ 输入症状总数」，保留 2 位小数 |
| 科室缺失取值 | 字符串 `"-"` | `null`（展示层的 `-` 由前端负责） |
| 子图深度参数 | `depth` 参数存在但无效，实际只返回一跳 | `depth` 真实生效，或该参数被移除；不得存在无效参数 |
| 图谱结果截断 | 算出 10 条，进提示词时静默截为 5 条 | 截断规则显式化并写入 trace；提示词与回传前端的条数关系在 `SKILL.md` 中声明 |
| 外部依赖不可用 | 检索或图谱不可用即整体失败 | **降级不阻断**：不可用的支路记为 `degraded`，问答继续，`done` 事件标注降级支路 |

### 3.7 可观测性约束

| 项 | 约束 |
|---|---|
| 记录对象 | **每一次 Skill 调用**与**每一次大模型调用** |
| 必录字段 | `trace_id`、Skill 名（或 `llm`）、耗时、输入摘要、输出摘要、Skill 路由决策 |
| 路由记录 | 每次编排必须记录本轮实际执行了哪些 Skill、跳过了哪些、跳过理由 |
| 存储 | 结构化存储，可按键检索、可按时间范围聚合 |
| 可回放 | 记录内容足以在**不重新调用外部依赖**的前提下重放一次完整问诊并比对结果 |
| 敏感信息 | 摘要字段不得完整落库患者原文与大模型完整输出；以长度受限的摘要 + 可配置的脱敏规则为准 |

### 3.8 回归测试约束

| 项 | 约束 |
|---|---|
| 时机 | 行为回归测试框架必须**从一开始就设计**，与功能同步交付，不作为后续补充 |
| 能力 | 支持**录制基线**与**回放对比** |
| 回放方式 | 回放时外部依赖（图数据库、向量索引、嵌入、大模型）由录制的响应替代，保证对比可复现 |
| 必输出指标 | **红旗拦截率**、**诊断漂移率**、**幻觉率**、**P95 延迟** |
| 用例集 | 版本化的固定输入集，随基线一同纳入版本控制 |

**四项指标的唯一定义**（指标不可自定义，否则不可比）：

| 指标 | 定义 | 目标 |
|---|---|---|
| 红旗拦截率 | 基线用例集中标记为「红旗」的用例，本次运行 `decision == intercept` 的比例 | **100%**（低于 100% 即为漏拦，视为阻断性失败） |
| 误拦率 | 基线用例集中标记为「非红旗」的用例，本次运行 `decision == intercept` 的比例（必须与拦截率同时报告） | **0%** |
| 诊断漂移率 | 基线用例集上，本次运行的候选疾病**有序列表**（前 `limit` 条）与基线不一致的用例比例 | 无硬性目标，趋势不得无故上升 |
| 幻觉率 | 答案中的**断言**无法在本次检索上下文找到依据的比例。断言抽取分两层：**确定性层**对数值、药品名、疾病名、检查名（依据图谱词表）做字面匹配；**判定层**对剩余自由文本由判定模型给出有据/无据。报告须同时给出 `deterministic_ratio`、`judged_ratio` 与 `total` | 无硬性目标，趋势不得无故上升 |
| P95 延迟 | 端到端耗时 95 分位，按路径分组统计：`intercepted`（被拦截）、`llm`（走完大模型）、`degraded`（含降级支路） | 分组报告，不合并 |

### 3.9 接口契约约束

所有前后端交互必须显式定义六项：**请求方法、路径、请求体 Schema、响应体 Schema、错误码、SSE 流式协议格式**。契约作为**独立 seam** 存在，两侧实现均以其为唯一依据。

### 3.10 文档语言与词汇

规格、`SKILL.md`、契约定义均使用中文正文，代码标识符、路径、字段名、枚举值保留原文。领域概念一律沿用 `FUNCTIONAL_SPEC.md` 附录 A 的术语表。

---

## 4. Seams

**Seam 的选择原则**：优先使用既有 seam；使用尽可能高的 seam；每一侧只保留**一个主 seam** 承载行为与回归断言，其余为**从属窄端口**，只为隔离外部资源与可观测性而存在，不承担业务断言。

### 4.1 后端 Seams

#### B-1　编排入口（主 Seam）

| 项 | 内容 |
|---|---|
| **位置** | `orchestration` Skill 的公开异步入口：接收一次问诊请求与请求上下文，产出规范化的 SSE 事件流（以及供回归使用的聚合结果） |
| **为什么是最高 seam** | 它之下包含安全门、归一化、双支路检索、上下文组装、大模型生成、trace 落库的全部行为。所有端到端断言、全部四项回归指标都在此计算 |
| **测什么** | 端到端行为：红旗拦截、单词表归一化、双支路并列、上下文组装、SSE 事件序列、降级、错误处理、trace 完整性 |
| **替身策略** | 不替换 B-1 本身；其下通过 B-3 的端口替换外部依赖 |
| **不测什么** | 不测各 Skill 的内部实现（词表的数据结构、查询语句的构造、提示词的文本排布） |

#### B-2　Skill 调用协议

| 项 | 内容 |
|---|---|
| **位置** | 统一的 `Skill.invoke(input) → output` 协议，及每次调用产出的 span |
| **测什么** | 每个 Skill 的四项声明：输入输出 Schema 校验、触发与跳过条件、边界情况处置、`SKILL.md` 测试用例逐条执行 |
| **为什么独立** | 五个 Skill 的边界是「可独立测试」这一目标的落点；没有这个 seam，Skill 化无法被验收 |
| **替身策略** | 纯计算型 Skill（归一化、安全门）无需替身；含 I/O 的 Skill（检索、图谱）通过 B-3 端口替换 |
| **不测什么** | 不测 Skill 之间的调用顺序（那是 B-1 的职责） |

#### B-3　外部资源端口

| 项 | 内容 |
|---|---|
| **位置** | 三个窄端口：`GraphPort`、`RetrievalPort`、`LlmPort` |
| **测什么** | 图谱查询语义、检索语义、以及**「大模型是否被调用」与「被调用的形态」** |
| **为什么独立** | ① 回归回放需要在不访问真实外部依赖的前提下重放；② 「红旗命中时大模型调用次数为 0」是一条硬性验收标准，必须在可计数的边界上断言 |
| **替身策略** | 测试用计数假实现；回放用记录回放实现 |
| **不测什么** | 不测驱动的重试、连接池、超时实现（属基础设施细节） |

#### B-4　追踪汇聚

| 项 | 内容 |
|---|---|
| **位置** | `TraceSink`：接收 span 并负责持久化 |
| **测什么** | trace 的**内容完整性**：trace_id 全局唯一、每次 Skill 调用与大模型调用恰好一条 span、必录字段齐全、路由决策被记录、摘要长度受约束 |
| **替身策略** | 内存录制 sink，断言写入内容而不触碰数据库 |
| **不测什么** | 不测存储表结构、索引、清理策略 |

#### B-5　持久化

| 项 | 内容 |
|---|---|
| **位置** | 异步会话与仓储层：每请求一个 `AsyncSession`，业务代码通过仓储访问数据 |
| **测什么** | 事务边界（回滚与提交）、并发下的计数正确性、只读查询的隔离 |
| **替身策略** | 测试库 + 每用例事务回滚 |
| **不测什么** | 不测 SQL 文本、不测 ORM 映射细节 |

### 4.2 前端 Seams

#### F-1　API 客户端（主 Seam）

| 项 | 内容 |
|---|---|
| **位置** | 唯一出口模块，封装全部 REST 调用与 SSE 消费 |
| **为什么是主 seam** | 所有视图只通过它与后端对话；它一旦正确，视图只需断言「调用了哪个方法、得到了什么状态」 |
| **测什么** | 每条契约的请求构造（方法、路径、查询参数、请求体）、响应解析（外壳拆解、分页、错误映射）、SSE 帧分发 |
| **替身策略** | 视图测试注入 API 客户端替身；客户端自身的测试注入 F-2 传输替身 |
| **不测什么** | 不测视图的 DOM 结构与样式 |

#### F-2　传输层

| 项 | 内容 |
|---|---|
| **位置** | 可注入的 HTTP / SSE 传输 |
| **测什么** | **契约一致性**（打桩的响应体形状符合契约即通过，不符合即失败）、SSE 帧解析与边界（分片到达、空帧、未知事件类型、连接中断） |
| **替身策略** | 录制回放：重放录制的后端响应 |
| **不测什么** | 不测重试策略与背压细节 |

#### F-3　守卫与鉴权状态

| 项 | 内容 |
|---|---|
| **位置** | 路由守卫 + 会话状态仓库 |
| **测什么** | 角色放行与拒绝、会话失效跳转、401 与 403 的分流（401 清理并跳登录；403 仅提示不跳转） |
| **替身策略** | 内存状态仓库，不触达真实存储 |
| **不测什么** | 不测令牌的签名与格式（那是后端职责） |

### 4.3 契约 Seam

#### C-1　接口契约

| 项 | 内容 |
|---|---|
| **位置** | 请求/响应 Schema 定义、错误码表、SSE 事件 Schema —— 独立于前后端两侧 |
| **测什么** | 双向一致性：后端产出的响应必须满足契约；前端对契约的解析必须能消费后端产出；SSE 每一帧必须满足事件 Schema |
| **为什么是独立 seam** | 它是「先定契约、两侧各自实现」的那条线。契约自身的变更必须独立可见，而不是散落在两侧的实现里 |
| **替身策略** | 无（契约即断言依据） |
| **不测什么** | 不测具体业务语义（那由 B-1 与视图各自断言） |

### 4.4 Seam 与回归框架的关系

| Seam | 在回归框架中的角色 |
|---|---|
| B-1 | 回放的**唯一驱动点**：输入用例集，产出聚合结果与四项指标 |
| B-3 | 回放的**可复现性来源**：以录制响应替代真实外部依赖 |
| B-4 | 回放的**证据来源**：trace 用于回答「这一轮走了哪些 Skill、为什么」 |
| B-2 | 回放的**归因粒度**：漂移可归因到具体 Skill |
| F-1 / F-2 | 前端侧的契约一致性回放 |
| C-1 | 两侧共同的校验基准 |

### 4.5 Seam 数量与取舍说明

全项目共 **9 个 seam**：后端 5（1 主 + 4 从属）、前端 3（1 主 + 2 从属）、契约 1（独立）。

取舍理由：若只保留 B-1 与 F-1 两个 seam，则「红旗命中时大模型调用次数为 0」「trace 必录字段齐全」「回放不触达外部依赖」三条验收标准都无法在不引入端口的情况下断言 —— 它们断言的对象正是 B-3 与 B-4。这四个从属端口不是设计偏好，而是四条硬性验收标准所要求的**最小可观测边界**。

---

## 5. 接口契约

### 5.1 通用约定

| 项 | 规定 |
|---|---|
| 基础路径 | `/api/v1` |
| 认证 | `Authorization: Bearer <access_token>` |
| 请求/响应编码 | `application/json; charset=utf-8`；文件上传为 `multipart/form-data` |
| 响应外壳 | `{"code": <int>, "message": <string>, "data": <object\|array\|null>}` |
| 分页载荷 | `data = {"items": [...], "total": <int>, "page": <int>, "page_size": <int>}` |
| 时间格式 | `YYYY-MM-DD HH:mm:ss`（日期为 `YYYY-MM-DD`） |
| 错误承载 | **错误码承载在真实 HTTP 状态码上，响应体 `code` 与之相同**。不使用「HTTP 200 + 业务错误码」的表达 |
| 幂等 | `GET` / `PUT` / `DELETE` 幂等；`POST` 非幂等 |
| 路径参数 | 资源编号为整数，非法格式返回 422 |
| 角色标记 | `user` / `doctor` / `admin`；`公开` 表示无需认证 |

### 5.2 错误码表

| HTTP | `code` | 含义 | 典型触发 |
|---|---|---|---|
| 200 | 200 | 成功 | — |
| 400 | 400 | 请求语义错误 | 角色类型非法、两次口令不一致 |
| 401 | 401 | 未认证或认证失效 | 无令牌、令牌无效或过期、令牌载荷不完整、账号不存在 |
| 403 | 403 | 已认证但无权限 | 角色不匹配、账号被禁用 |
| 404 | 404 | 资源不存在 | 目标编号无对应记录 |
| 409 | 409 | 状态冲突 | 用户名已存在、科室名已存在、同一会话已有生成中的请求 |
| 413 | 413 | 载荷过大 | 上传文件超过配置上限 |
| 422 | 422 | 参数校验失败 | 字段缺失、长度越界、类型错误、查询参数越界 |
| 500 | 500 | 服务内部错误 | 未预期异常 |
| 502 | 502 | 上游返回非法 | 上游依赖返回不可解析结果 |
| 503 | 503 | 上游不可用 | 大模型或嵌入服务完全不可用（可用时降级为 200 + `degraded` 标记） |
| 504 | 504 | 上游超时 | 大模型生成超时 |

**降级与失败的区分**：向量检索与图谱推理属于增强支路，其不可用**不**产生错误码，而是继续问答并在响应中标注 `degraded: ["retrieval"] / ["graph"]`。大模型生成不可用无法降级，返回 503 / 504。

### 5.3 Schema 索引

| Schema | 用途 | 字段 |
|---|---|---|
| `LoginRequest` | 登录 | `username: str(必填)`, `password: str(必填)`, `role: "user"\|"doctor"\|"admin"(必填)` |
| `RegisterRequest` | 患者注册 | `username: str(3..50)`, `password: str(≥6)`, `confirm_password: str(≥6)`, `real_name?: str`, `phone?: str` |
| `TokenResponse` | 登录/注册成功 | `access_token: str`, `token_type: "bearer"`, `role: str`, `user_id: int`, `username: str`, `display_name: str`, `avatar: str\|null` |
| `PasswordChangeRequest` | 改密 | `old_password: str`, `new_password: str` |
| `ProfileUpdateRequest` | 改资料 | `nickname?`, `real_name?`, `phone?`, `email?`, `gender?`, `age?`, `allergy_history?`, `title?`, `specialty?`, `introduction?`（均为可选） |
| `UserCreateRequest` | 建患者 | `username: str(3..50)`, `password: str(≥6)`, `confirm_password: str(≥6)`, `real_name?`, `gender: int=1`, `age?`, `phone?`, `allergy_history?`, `status: int=1` |
| `UserUpdateRequest` | 改患者 | 上表除 `username` 外全部可选，另含 `password?`, `confirm_password?` |
| `DoctorCreateRequest` | 建医生 | `username: str(3..50)`, `password: str(≥6)`, `confirm_password: str(≥6)`, `real_name: str(1..50)`, `department_id?`, `title?`, `specialty?`, `introduction?`, `phone?`, `status: int=1` |
| `DoctorUpdateRequest` | 改医生 | 上表除 `username`/`password` 外全部可选，另含 `password?`, `confirm_password?` |
| `DepartmentRequest` | 建/改科室 | `name: str(1..50)`, `description?: str(≤255)`, `sort_order: int=0` |
| `ChatRequest` | 发起问诊 | `session_id: int\|null`, `message: str(≥1)`, `explicit_symptoms?: string[]` |
| `GraphQueryRequest` | 症状推理 | `symptoms: string[]`（至少 1 项） |
| `ConsultCreateRequest` | 发起人工问诊 | `doctor_id: int\|null`, `chief_complaint: str(≥1)` |
| `ConsultReplyRequest` | 医生回复 | `consult_id: int`, `content: str(≥1)` |
| `AppointmentCreateRequest` | 新建预约 | `doctor_id: int`, `department_id: int`, `visit_date: date`, `time_slot: str`, `remark?: str(≤255)` |
| `HealthRecordCreateRequest` | 建档案 | `user_id: int`, `record_type: str(1..50)`, `diagnosis?`, `treatment?`, `prescription?`, `visit_date?: date` |
| `HealthRecordUpdateRequest` | 改档案 | 上表除 `user_id` 外全部可选 |
| `ArticleRequest` | 建/改文章 | `title: str(1..200)`, `category?: str(≤50)`, `summary?: str(≤500)`, `content?: str`, `status: int=1` |
| `NoticeRequest` | 建/改公告 | `title: str(1..200)`, `content: str=""`, `status: int=1` |
| `PageQuery` | 分页查询 | `page: int≥1`, `page_size: int(1..100)`, `keyword?: str` |
| `TraceQuery` | 追踪检索 | `trace_id?: str`, `skill?: str`, `from?: datetime`, `to?: datetime`, `degraded?: bool`, `page`, `page_size` |
| `RegressionRunRequest` | 触发回放 | `case_set_version: str`, `baseline_version: str`, `label?: str` |
| `MetricsReport` | 四项指标 | `redflag_intercept_rate: float`, `redflag_false_positive_rate: float`, `diagnosis_drift_rate: float`, `hallucination: {deterministic_ratio: float, judged_ratio: float, total: float}`, `latency: {intercepted: {p50: int, p95: int}, llm: {...}, degraded: {...}}`, `case_count: int` |

### 5.4 REST 端点契约

**认证与个人中心**

| 方法 | 路径 | 角色 | 请求体 | 响应体 | 错误码 |
|---|---|---|---|---|---|
| POST | `/auth/login` | 公开 | `LoginRequest` | `TokenResponse` | 400, 401, 403, 422 |
| POST | `/auth/register` | 公开 | `RegisterRequest` | `TokenResponse` | 400, 409, 422 |
| GET | `/profile/info` | 任意已认证 | — | `ProfileView`（按角色字段不同） | 401 |
| PUT | `/profile/update` | 任意已认证 | `ProfileUpdateRequest` | `null` | 401, 422 |
| PUT | `/profile/password` | 任意已认证 | `PasswordChangeRequest` | `null` | 400, 401, 422 |
| POST | `/profile/avatar` | 任意已认证 | `multipart(file)` | `{avatar: str}` | 401, 413, 422 |

**患者与医生主数据**

| 方法 | 路径 | 角色 | 请求体 | 响应体 | 错误码 |
|---|---|---|---|---|---|
| GET | `/users` | `admin` | `PageQuery` | 分页 `UserView[]` | 401, 403, 422 |
| POST | `/users` | `admin` | `UserCreateRequest` | `UserView` | 401, 403, 409, 422 |
| PUT | `/users/{id}` | `admin` | `UserUpdateRequest` | `UserView` | 401, 403, 404, 422 |
| DELETE | `/users/{id}` | `admin` | — | `null` | 401, 403, 404 |
| PUT | `/users/{id}/status` | `admin` | `{status: int}` | `null` | 401, 403, 404, 422 |
| GET | `/doctors` | 公开 | `PageQuery` + `department_id?` | 分页 `DoctorView[]` | 422 |
| GET | `/doctors/admin` | `admin` | `PageQuery` | 分页 `DoctorView[]` | 401, 403, 422 |
| POST | `/doctors` | `admin` | `DoctorCreateRequest` | `DoctorView` | 401, 403, 409, 422 |
| PUT | `/doctors/{id}` | `admin` | `DoctorUpdateRequest` | `DoctorView` | 401, 403, 404, 422 |
| DELETE | `/doctors/{id}` | `admin` | — | `null` | 401, 403, 404 |
| PUT | `/doctors/{id}/status` | `admin` | `{status: int}` | `null` | 401, 403, 404, 422 |
| GET | `/departments` | 公开 | — | `DepartmentView[]` | — |
| GET | `/departments/admin` | `admin` | `PageQuery` | 分页 `DepartmentView[]` | 401, 403, 422 |
| POST | `/departments` | `admin` | `DepartmentRequest` | `{id: int}` | 401, 403, 409, 422 |
| PUT | `/departments/{id}` | `admin` | `DepartmentRequest` | `null` | 401, 403, 404, 409, 422 |
| DELETE | `/departments/{id}` | `admin` | — | `null` | 401, 403, 404, 409 |

> `409` 在删除科室时表示「该科室下仍有医生」。

**AI 问诊与知识库**

| 方法 | 路径 | 角色 | 请求体 | 响应体 | 错误码 |
|---|---|---|---|---|---|
| GET | `/chat/sessions` | `user` | — | `SessionView[]` | 401, 403 |
| GET | `/chat/sessions/{id}/messages` | `user` | — | `MessageView[]` | 401, 403, 404 |
| POST | `/chat/send` | `user` | `ChatRequest` | **SSE 流**（见 5.5） | 401, 403, 409, 422, 503, 504 |
| GET | `/chat/admin/sessions` | `admin` | `PageQuery` | 分页 `SessionView[]` | 401, 403, 422 |
| GET | `/knowledge` | `admin` | `PageQuery` | 分页 `KnowledgeFileView[]` | 401, 403, 422 |
| POST | `/knowledge` | `admin` | `multipart(file)` | `{id: int, file_name: str}` | 401, 403, 413, 422 |
| POST | `/knowledge/{id}/revectorize` | `admin` | — | `null` | 401, 403, 404 |
| DELETE | `/knowledge/{id}` | `admin` | — | `null` | 401, 403, 404 |

> `409` 在 `/chat/send` 表示「同一会话已有生成中的请求」。

**知识图谱**

| 方法 | 路径 | 角色 | 请求体 | 响应体 | 错误码 |
|---|---|---|---|---|---|
| POST | `/graph/infer` | `user`/`doctor`/`admin` | `GraphQueryRequest` | `DiseaseCandidate[]` | 401, 403, 422, 503 |
| GET | `/graph/diseases/{name}` | 公开 | — | `DiseaseDetailView` | 404, 503 |
| GET | `/graph/entities/{name}/neighbors` | 公开 | `depth?` | `GraphView` | 404, 422, 503 |
| GET | `/graph/search` | 公开 | `keyword: str` | `GraphEntityView[]` | 422, 503 |
| GET | `/graph` | 公开 | — | `GraphView` | 503 |
| GET | `/graph/stats` | `admin` | — | `Record<string, int>` | 401, 403, 503 |

**人工问诊**

| 方法 | 路径 | 角色 | 请求体 | 响应体 | 错误码 |
|---|---|---|---|---|---|
| POST | `/consults` | `user` | `ConsultCreateRequest` | `{id: int}` | 401, 403, 422 |
| GET | `/consults/my` | `user` | — | `ConsultView[]` | 401, 403 |
| GET | `/consults/pending` | `doctor` | — | `ConsultView[]` | 401, 403 |
| POST | `/consults/{id}/replies` | `doctor` | `ConsultReplyRequest` | `null` | 401, 403, 404, 409, 422 |
| GET | `/consults/admin` | `admin` | `PageQuery` + `status?` | 分页 `ConsultView[]` | 401, 403, 422 |
| DELETE | `/consults/admin/{id}` | `admin` | — | `null` | 401, 403, 404 |

> `409` 在回复时表示「该工单已被其他医生认领」（新项目收紧：原实现允许任何医生回复任意工单）。

**预约与健康档案**

| 方法 | 路径 | 角色 | 请求体 | 响应体 | 错误码 |
|---|---|---|---|---|---|
| POST | `/appointments` | `user` | `AppointmentCreateRequest` | `{id: int}` | 401, 403, 422 |
| GET | `/appointments/my` | `user` | — | `AppointmentView[]` | 401, 403 |
| GET | `/appointments/doctor` | `doctor` | — | `AppointmentView[]` | 401, 403 |
| GET | `/appointments/admin` | `admin` | `PageQuery` + `department_id?` + `visit_date?` + `status?` | 分页 `AppointmentView[]` | 401, 403, 422 |
| PUT | `/appointments/{id}/status` | `admin`/`doctor` | `{status: int}` | `null` | 401, 403, 404, 422 |
| DELETE | `/appointments/admin/{id}` | `admin` | — | `null` | 401, 403, 404 |
| GET | `/records/my` | `user` | — | `HealthRecordView[]` | 401, 403 |
| GET | `/records/doctor` | `doctor` | — | `HealthRecordView[]` | 401, 403 |
| GET | `/records/doctor/patient-options` | `doctor` | — | `{id: int, name: str}[]` | 401, 403 |
| POST | `/records/doctor` | `doctor` | `HealthRecordCreateRequest` | `HealthRecordView` | 401, 403, 404, 422 |
| PUT | `/records/doctor/{id}` | `doctor` | `HealthRecordUpdateRequest` | `HealthRecordView` | 401, 403, 404, 422 |
| DELETE | `/records/doctor/{id}` | `doctor` | — | `null` | 401, 403, 404 |

**内容与统计**

| 方法 | 路径 | 角色 | 请求体 | 响应体 | 错误码 |
|---|---|---|---|---|---|
| GET | `/articles` | 公开 | `PageQuery` + `category?` | 分页 `ArticleListView[]` | 422 |
| GET | `/articles/{id}` | 公开 | — | `ArticleView` | 404 |
| GET | `/articles/admin` | `admin` | `PageQuery` | 分页 `ArticleView[]` | 401, 403, 422 |
| POST | `/articles` | `admin` | `ArticleRequest` | `{id: int}` | 401, 403, 422 |
| PUT | `/articles/{id}` | `admin` | `ArticleRequest` | `null` | 401, 403, 404, 422 |
| DELETE | `/articles/{id}` | `admin` | — | `null` | 401, 403, 404 |
| GET | `/notices` | 公开 | — | `NoticeView[]` | — |
| GET | `/notices/{id}` | 公开 | — | `NoticeView` | 404 |
| GET | `/notices/admin` | `admin` | `PageQuery` | 分页 `NoticeView[]` | 401, 403, 422 |
| POST | `/notices` | `admin` | `NoticeRequest` | `{id: int}` | 401, 403, 422 |
| PUT | `/notices/{id}` | `admin` | `NoticeRequest` | `null` | 401, 403, 404, 422 |
| DELETE | `/notices/{id}` | `admin` | — | `null` | 401, 403, 404 |
| GET | `/stat/overview` | `admin`/`doctor` | — | `StatOverviewView`（按角色字段不同） | 401, 403 |
| GET | `/stat/user-overview` | `user` | — | `UserStatView` | 401, 403 |
| GET | `/stat/consult-trend` | `admin` | `days: int=7` | `{date, count}[]` | 401, 403, 422 |
| GET | `/stat/appointments-by-department` | `admin` | — | `{name, value}[]` | 401, 403 |
| GET | `/stat/user-growth` | `admin` | `days: int=7` | `{date, count}[]` | 401, 403, 422 |
| GET | `/stat/knowledge-types` | `admin` | — | `{name, value}[]` | 401, 403 |

**可观测性与回归**

| 方法 | 路径 | 角色 | 请求体 | 响应体 | 错误码 |
|---|---|---|---|---|---|
| GET | `/traces/{trace_id}` | `admin` | — | `TraceView`（含全部 span 与路由决策） | 401, 403, 404 |
| GET | `/traces` | `admin` | `TraceQuery` | 分页 `TraceSummaryView[]` | 401, 403, 422 |
| GET | `/skills` | 任意已认证 | — | `SkillManifestView[]`（五个 Skill 的名称、类别、Schema 版本、词表版本） | 401 |
| POST | `/regression/runs` | `admin` | `RegressionRunRequest` | `{run_id: str}` | 401, 403, 404, 422 |
| GET | `/regression/runs/{run_id}` | `admin` | — | `{status, metrics: MetricsReport\|null}` | 401, 403, 404 |
| GET | `/regression/baselines` | `admin` | — | `BaselineView[]`（可用基线版本清单） | 401, 403 |

### 5.5 SSE 流式协议

**端点**：`POST /api/v1/chat/send`
**响应头**：`Content-Type: text/event-stream; charset=utf-8`、`Cache-Control: no-cache`、`X-Accel-Buffering: no`
**帧格式**：每帧为 `data: <JSON>\n\n`；JSON 使用 UTF-8，不转义非 ASCII 字符。事件类型由 JSON 内的 `type` 字段区分，不使用 SSE 的 `event:` 字段。

| `type` | 载荷字段 | 出现时机 | 出现次数 |
|---|---|---|---|
| `session` | `session_id: int` | 流的第 1 帧 | 恰好 1 次 |
| `trace` | `trace_id: str` | 第 2 帧 | 恰好 1 次 |
| `route` | `skills_run: string[]`, `skills_skipped: {skill: str, reason: str}[]` | 路由决策完成后 | 恰好 1 次（拦截路径下 `skills_run` 只含 `safety-gate`） |
| `safety` | `decision: "intercept"`, `level: "emergency"\|"urgent"`, `red_flags: {id, label, matched_surface, severity}[]`, `message: str`, `suggested_action: str` | 仅当安全门拦截 | 0 或 1 次 |
| `content` | `content: str` | 生成过程中逐段推送 | 0..N 次 |
| `done` | `references: Reference[]`, `graph: DiseaseCandidate[]`, `coverage_note: str\|null`, `degraded: string[]`, `cost_time: int`, `trace_id: str` | 正常结束 | 恰好 1 次 |
| `error` | `code: int`, `message: str`, `trace_id: str` | 异常结束 | 0 或 1 次 |

**协议不变量**（可测）：

1. `session` 与 `trace` 必为前两帧，且顺序固定。
2. 拦截路径下：`safety` 帧出现，`content` 帧次数为 0，`route.skills_run == ["safety-gate"]`，`done` 帧的 `references == []` 且 `graph == []`。
3. 正常路径下：`safety` 帧不出现，`done` 帧恰好 1 次。
4. `done` 与 `error` 互斥，且流以二者之一结束。
5. 任何帧的 `trace_id` 与 `trace` 帧一致。
6. 未知 `type` 的帧必须被前端忽略而不中断流（向前兼容）。

**引用与候选载荷**

| 载荷 | 字段 |
|---|---|
| `Reference` | `index: int`, `file_name: str`, `snippet: str`（正文前 200 字符） |
| `DiseaseCandidate` | `disease: str`, `match_count: int`, `coverage: float`, `department: str\|null`, `matched_symptoms: string[]` |

### 5.6 契约的机器可读来源与双向校验

| 项 | 规定 |
|---|---|
| REST 契约来源 | 后端框架的 Schema 定义产出的机器可读接口描述文件，作为唯一事实来源 |
| SSE 契约来源 | 独立的 SSE 事件 Schema 定义文件（与 REST 描述并列存放于契约目录） |
| 前端消费 | 前端的类型定义与运行时校验器由同一份契约生成或校验，不得手写第二份 |
| 双向校验 | 后端契约测试断言实际响应满足 Schema；前端契约测试断言能解析契约中声明的全部形状，含全部错误码分支与全部 SSE 帧类型 |
| 契约变更 | 契约文件的变更必须独立可见；破坏性变更需提升契约版本号 |

---

## 6. Acceptance Criteria

所有验收标准必须是**可执行、可观察、可复现**的。每条给出明确的断言对象与通过条件。

### 6.1 后端验收标准

#### Skill 化

| ID | 验收标准 |
|---|---|
| AC-B-01 | 存在 5 份 `SKILL.md`，文件名与 Skill 名一致；每份均含「输入输出 Schema」「触发条件」「边界情况」「测试用例」四节 |
| AC-B-02 | 每份 `SKILL.md` 中的测试用例均被转化为可执行测试，且全部通过 |
| AC-B-03 | 每个 Skill 的输入与输出均按其声明 Schema 校验；构造不符合 Schema 的输入时，Skill 返回校验失败而非静默继续 |
| AC-B-04 | 除 `orchestration` 外，其余四个 Skill 在测试中以「大模型端口被替换为抛异常的假实现」运行，全部测试仍通过（证明它们不调用大模型） |
| AC-B-05 | 五个 Skill 可被单独实例化并单独调用，不需要启动关系库、图库、向量索引 |

#### 安全门

| ID | 验收标准 |
|---|---|
| AC-B-06 | 对标记为红旗的输入，SSE 流中出现 `safety` 帧且 `decision == intercept` |
| AC-B-07 | 对同一红旗输入，`LlmPort` 的调用次数为 **0** |
| AC-B-08 | 对同一红旗输入，`GraphPort` 与 `RetrievalPort` 的调用次数均为 **0**（全链路短路） |
| AC-B-09 | 对同一红旗输入，归一化 Skill 的调用次数为 **0** |
| AC-B-10 | 对非红旗输入，`safety` 帧不出现，且流中出现 `content` 帧 |
| AC-B-11 | 安全门为确定性实现：同一输入连续运行 100 次，`decision` 与 `red_flags` 完全一致 |
| AC-B-12 | 否定式表述（如「没有胸痛」「不发烧」）不触发拦截 |
| AC-B-13 | 多条红旗同时命中时，`red_flags` 返回全部命中项，`level` 取最高严重级 |
| AC-B-14 | `decision == intercept` 时 `message` 与 `suggested_action` 均非空 |
| AC-B-15 | trace 中记录命中的红旗标识、匹配到的原文片段与规则版本号 |
| AC-B-16 | 红旗用例集的拦截率为 **100%**，非红旗用例集的误拦率为 **0%**（由回归框架输出，见 AC-B-27） |

#### 归一化与词汇统一

| ID | 验收标准 |
|---|---|
| AC-B-17 | 归一化只使用**一份**词表；代码库中不存在第二份症状列表或第二份别名表 |
| AC-B-18 | 22 条别名映射在 `/chat/send` 链路与 `/graph/infer` 链路下的归一化结果**完全一致**（同一输入，两条链路输出同一标准症状集合） |
| AC-B-19 | 口语输入「头疼」「肚子痛」「拉肚子」「嗓子痛」在 `/chat/send` 链路下均产生非空的标准症状集合，并触发图谱推理 |
| AC-B-20 | 同一症状多次出现时去重且保留首次出现位置；别名与标准词同时出现时合并为一项 |

#### 编排与异步

| ID | 验收标准 |
|---|---|
| AC-B-21 | 路由为确定性：同一输入、同一配置下，`route.skills_run` 与 `route.skills_skipped` 完全一致 |
| AC-B-22 | 正常路径下 `skills_run` 恰好包含 `safety-gate`、`symptom-normalization`、`vector-retrieval`、`graph-inference`、`orchestration` |
| AC-B-23 | 归一化输出为空时，`graph-inference` 被跳过，且 `skills_skipped` 中给出理由 |
| AC-B-24 | 请求路径中不存在同步阻塞 I/O：以阻塞调用检测（在事件循环上监测阻塞时长）验证，并发 20 个问诊请求时单次阻塞时长不超过配置阈值 |
| AC-B-25 | 同一会话并发发起两个 `/chat/send`：第二个请求返回 409，且不产生并行的生成 |
| AC-B-26 | 客户端中途断开时，下游大模型调用被取消，trace 中该 span 状态为 `cancelled` |
| AC-B-27 | 向量检索或图谱不可用时：问答仍完成，`done.degraded` 列出不可用支路，HTTP 状态仍为 200 |

#### 可观测性

| ID | 验收标准 |
|---|---|
| AC-B-28 | 每次 Skill 调用恰好产生一条 span；每次大模型调用恰好产生一条 span |
| AC-B-29 | 每条 span 含 `trace_id`、Skill 名、耗时、输入摘要、输出摘要；`trace_id` 在一次问诊内全局一致 |
| AC-B-30 | 每次编排产生一条路由记录，含实际执行的 Skill 列表、跳过的 Skill 列表与跳过理由 |
| AC-B-31 | 摘要字段长度受配置上限约束；患者原文与大模型完整输出不以完整形式落库 |
| AC-B-32 | 可按 `trace_id` 检索出一次问诊的全部 span 与路由记录，并按时间顺序还原 |
| AC-B-33 | 一次问诊的 trace 足以在不访问外部依赖的前提下重放该次问诊并得到相同结果 |

#### 回归框架

| ID | 验收标准 |
|---|---|
| AC-B-34 | 存在一条命令录制基线，产出包含输入集、各 Skill 输出、最终结果与耗时的版本化基线 |
| AC-B-35 | 存在一条命令回放对比，回放期间不访问图库、向量索引、嵌入服务与大模型（以调用计数为 0 断言） |
| AC-B-36 | 回放输出 `MetricsReport`，含红旗拦截率、误拦率、诊断漂移率、幻觉率、P95 延迟五项 |
| AC-B-37 | 幻觉率报告同时给出 `deterministic_ratio`、`judged_ratio` 与 `total` |
| AC-B-38 | P95 延迟按 `intercepted`、`llm`、`degraded` 三条路径**分组**输出，不合并 |
| AC-B-39 | 对同一基线与同一代码重复回放两次，四项指标完全一致（回放可复现） |
| AC-B-40 | 诊断漂移率在代码未变更时回放结果为 **0** |

#### 契约与功能对等

| ID | 验收标准 |
|---|---|
| AC-B-41 | 每个端点的实际响应均满足契约 Schema（含成功与全部错误码分支） |
| AC-B-42 | 每个 SSE 帧均满足事件 Schema；协议不变量（5.5 节 6 条）逐条通过 |
| AC-B-43 | 错误码使用真实 HTTP 状态码；响应体 `code` 与 HTTP 状态一致；不存在「HTTP 200 + 非 200 的 `code`」 |
| AC-B-44 | `FUNCTIONAL_SPEC.md` 保留项逐条通过回归：14 实体语义、三角色模型、状态值、级联删除范围与顺序、科室删除保护、档案归属校验、主诉编码约定、会话标题与消息计数规则、分页外壳 |
| AC-B-45 | 3.6 节「有意修复」六项逐条通过：单词表、`coverage` 更名、科室缺失为 `null`、无无效参数、截断规则显式、降级不阻断 |
| AC-B-46 | `probability` 字段在契约与代码中均不存在；对外字段名为 `coverage` |

### 6.2 前端验收标准

| ID | 验收标准 |
|---|---|
| AC-F-01 | 前端不引入任何后端连接串、数据库客户端或图数据库客户端；依赖清单中不存在此类依赖 |
| AC-F-02 | 全部后端调用经由 F-1 单一出口模块；视图层不存在直接的传输调用 |
| AC-F-03 | 每条契约（含全部错误码分支与全部 SSE 帧类型）在前端侧有对应的契约测试，且全部通过 |
| AC-F-04 | F-2 传输层收到符合契约的响应即通过；收到形状不符的响应时契约测试失败 |
| AC-F-05 | SSE 解析正确处理：分片到达（一帧跨多次读取）、一次读取含多帧、空帧、未知 `type` 被忽略、连接中断被捕获 |
| AC-F-06 | 红旗拦截时，界面展示安全提示，且**不展示**任何生成内容占位、引用区或候选疾病区 |
| AC-F-07 | 401 响应：清理本地鉴权并跳转登录页 |
| AC-F-08 | 403 响应：仅展示错误提示，**不**清理鉴权、**不**跳转 |
| AC-F-09 | 路由守卫按角色放行与拒绝；未知角色清理鉴权并跳转登录页 |
| AC-F-10 | 侧边菜单按角色生成：管理员 10 项、医生 4 项；个人中心仅从用户下拉进入 |
| AC-F-11 | 状态展示映射正确：预约 0–3、工单 0/1、账号 0/1、向量化 0–3、图谱关系名与节点类型；未知值回退到既定默认值 |
| AC-F-12 | 分页列表在删除最后一条时页码回退；列表加载失败展示空状态 |
| AC-F-13 | 知识库列表在存在向量化状态为 0 或 1 的行时按配置间隔轮询，全部完成后停止，组件卸载时清除定时器 |
| AC-F-14 | 诊断漂移率相关的候选疾病区按 `coverage` 排序展示，`coverage` 缺失时不展示进度条而非展示 0% |
| AC-F-15 | 主诉编码：提交时按 `标题：正文` 拼接（全角冒号）；医生端按第一个全角冒号拆回，无冒号时整串作为标题 |
| AC-F-16 | 前端全部表单校验在契约校验失败时以前端提示呈现，且前端校验**不**作为唯一依据（构造绕过前端校验的请求仍被后端以 422 拒绝） |

### 6.3 端到端验收场景

| ID | 场景 | 期望 |
|---|---|---|
| AC-E-01 | 患者输入「我头疼发烧三天了」 | `safety=allow`；归一化产出含 `头痛`、`发热`；图谱返回候选疾病；`content` 帧非空；`done` 含引用与候选；trace 含 5 条 Skill span + 1 条大模型 span |
| AC-E-02 | 患者输入「胸口剧痛，出冷汗，喘不上气」 | `safety=intercept`；`content` 帧 0 次；`done.references` 与 `done.graph` 为空；trace 中只有 `safety-gate` 一条 Skill span，无大模型 span |
| AC-E-03 | 患者输入「我没有胸痛，只是有点咳嗽」 | `safety=allow`；正常生成 |
| AC-E-04 | 图谱不可用，患者输入「头疼发烧」 | HTTP 200；`done.degraded` 含 `graph`；回答仍生成 |
| AC-E-05 | 管理员上传一份 `.pdf` 知识文件 | 返回 `{id, file_name}`；状态从「已上传」→「处理中」→「已向量化」；分块数与向量条目数一致 |
| AC-E-06 | 医生删除他人名下的健康档案 | 404，且档案未被删除 |
| AC-E-07 | 管理员删除仍有关联医生的科室 | 409，且科室未被删除 |
| AC-E-08 | 删除患者 | 其会话与消息、工单与回复、预约、档案按既定顺序全部删除 |
| AC-E-09 | 录制基线后不加改动直接回放 | 四项指标：拦截率 100%、误拦率 0%、漂移率 0%、`judged_ratio` 与基线一致 |

---

## 7. Out of Scope

以下内容**明确不在**本规格范围内。列出是为了让边界可见，而非暗示应当实施。

### 7.1 凭据与传输加固

`FUNCTIONAL_SPEC.md` 附录 B.2 记录的现状**原样保留**，本规格不做任何处理：

- 口令的明文存储与明文比对
- 令牌签名密钥、关系库口令、图库口令的硬编码
- 跨域策略 `allow_origins=["*"]` 与 `allow_credentials=True` 并存
- 除大模型密钥外无任何配置来自环境变量

### 7.2 越权可表达路径（一处例外）

`FUNCTIONAL_SPEC.md` 附录 B.1 记录的两条路径：

| 路径 | 本规格的处理 |
|---|---|
| 任一患者可读取任意会话号的消息正文 | **不在范围内**，原样保留 |
| 任一医生可回复任意工单 | **纳入范围**（见 5.4 节 `/consults/{id}/replies` 的 409 语义与 AC-E-06 相关的归属校验） |

四个无需登录的图谱只读接口（`/graph`、`/graph/search`、`/graph/entities/{name}/neighbors`、`/graph/diseases/{name}`）**保持公开**，不纳入权限收紧。

### 7.3 其余逻辑失效点

`FUNCTIONAL_SPEC.md` 附录 B.3 中未被第 3.6 节「有意修复」列入的条目，一律保持现状，包括但不限于：图谱结果的提示词截断以外的截断行为、状态迁移无校验、文章与公告更新删除不校验存在性、预约状态接口在记录不存在时的成功返回语义（本规格已将其改为 404，属契约收紧，除此之外不扩展）。

### 7.4 数据内容治理

- 图数据库内容的混合语言节点名（如 `慢性 daily 头痛`）与首尾未清理的字符串
- 同名跨标签节点（`失眠`、`贫血`、`骨折`、`高血压` 同为疾病与症状节点）
- 同时出现在「宜吃」与「忌吃」中的食物节点
- 84 个仅有名称、无任何其他关联的并发症节点
- 图谱医学内容的扩充、审核与临床校验

### 7.5 产品与业务范围

- 多租户、多机构、多院区
- 国际化与多语言界面
- 移动端原生应用、小程序、桌面端
- 支付、处方流转、药品库存、医保对接
- 视频问诊、即时通讯、推送通知
- 评价与评分体系
- 真实医学有效性验证与临床验证

### 7.6 工程与运维

- 容器化、编排、CI/CD 流水线
- 部署拓扑、容量规划、限流与熔断策略（除 5.2 节列出的错误码语义外）
- 监控告警、值班、故障演练
- 数据备份、归档、清理与合规留存策略
- trace 数据的保留期与冷热分层

### 7.7 前端范围

- 视觉设计、品牌与主题定制
- 无障碍（a11y）达标
- 前端性能预算与首屏优化指标
- 服务端渲染或静态站点生成

### 7.8 数据迁移

- 从现有系统迁移历史数据
- 关系库建表脚本缺失（`server/sql/db_ai_medical.sql`）的补全
- 现有向量索引的重建与兼容

新项目从空库开始，仅通过图谱灌数脚本与知识库种子文档初始化。

### 7.9 提示词与模型选型

- 提示词的迭代调优
- 大模型与嵌入模型的选型对比、切换与灰度
- 温度、最大长度等生成参数的调优

本规格只要求提示词的**组装规则**（安全约束的 4 条、上下文注入位置、历史截断条数）与现状一致且可回放，不涉及提示词内容的优化。

---

## 附：Skill 清单与契约要点

各 Skill 的完整契约见其 `SKILL.md`。下表是编排视角下的路由与顺序约束。

| 顺序 | Skill | 类别 | 触发条件 | 大模型调用 | 本规格新增的关键约束 |
|---|---|---|---|---|---|
| 1 | `safety-gate` | Process Rules | **恒首先执行**，无前置条件 | 否 | 命中即全链路短路；确定性可复现；记录匹配片段与规则版本 |
| 2 | `symptom-normalization` | 能力 | 安全门通过后恒执行 | 否 | 唯一词表；22 条别名在两条链路同等生效；否定式不计入 |
| 3a | `vector-retrieval` | 能力 | 归一化后执行，**与 3b 并行** | 否 | 不可用时降级不阻断；记录每条命中的距离 |
| 3b | `graph-inference` | 能力 | 归一化输出非空时执行，**与 3a 并行** | 否 | `coverage` 语义与 2 位小数；`department` 缺失为 `null`；无最低命中阈值 |
| 4 | `orchestration` | 编排 | 每次问诊请求 | **是（唯一）** | 路由确定性；同会话并发返回 409；客户端断开时取消下游调用；产出完整 trace |
