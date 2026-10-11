# MediSentinel · AI 智能医疗问诊平台

> 一个把 AI 问诊链路**拆成五个可独立测试的 Skill** 的重构项目：安全门、症状归一化、向量检索、图谱推理、编排。后端全异步（FastAPI + SQLAlchemy 2.0 + Neo4j + Chroma），前端 Vue 3 三端（患者门户 / 医生工作台 / 管理后台）共用一套设计令牌。

这里的重点不是「接一个大模型」，而是**确定性优先**的工程取舍：安全判断、症状归一化、图谱推理全部由确定性规则完成，大模型只负责最后的自然语言组织；每一次调用都留痕，可在不触达外部依赖的前提下回放整次问诊。

## 核心特性

- 🛡️ **安全先行** —— 红旗症状在**调用大模型之前**确定性拦截，命中即全链路短路（归一化 / 检索 / 图谱 / 生成都不执行），并经 trace 审计。
- 🧩 **五 Skill 编排** —— 每个 Skill 有独立契约（输入输出 Schema / 触发条件 / 边界情况 / 测试用例），可脱离关系库、图库单独实例化测试。
- 🔎 **双支路 RAG，检索侧做混合** —— 向量检索与图谱推理**并行且互不筛选**；检索端口内部再融合 **BM25 + 向量（RRF）** 并按阈值过滤，离题问句直接返回空结果而不是硬塞 5 条。本地 ONNX 交叉编码器重排已实现、**默认关闭**（见「量化结果」里的取舍）。任一支路不可用即降级（`degraded`），问答继续而不是整体失败。
- 📏 **检索质量可量** —— 30 条人工标注 query-文档对（`retrieval-v1`，冻结后不回溯改标签），一条命令给出 `recall@1` / `recall@5` / `MRR`；有对照才让"要不要上重排"这类问题有答案。
- 🔁 **业务闭环** —— 患者转人工可**带上 AI 会话**，医生在工单里直接看到 AI 的候选疾病与引用；确认后可把结论**沉淀为档案**（标注来源 `ai` / `doctor`、可撤回）；档案再**反哺下一次问诊的提示词**（限长 + 围栏 + 注入声明）。
- 🧯 **降级容错** —— 生成侧只在**首字节之前**重试（指数退避；已吐字绝不重试，否则前端会看到拼接内容），主模型不可用且未吐字时**故障转移**到备用模型（同一 key 换模型名）；两者都不改既有的 503 / 504 契约。
- 🧾 **可回放 trace** —— 每次 Skill 与大模型调用都留下结构化 span，足以在不访问外部依赖的前提下重放一次问诊并比对结果。
- 🎨 **三端一致 UI** —— 患者 / 医生 / 管理端共用设计令牌（紫色渐变主色、深色侧边栏、卡片化内容区），Element Plus 按需引入。

## 量化结果（可引用）

每个数字都带**口径**（分母是什么、样本多少）。完整清单与「不可引用」项见
[`.scratch/agentic-consult/METRICS.md`](./.scratch/agentic-consult/METRICS.md)——
**对外引用以那一页为准**。

| 指标 | 值 | 口径 |
|---|---|---|
| 知识库规模 | 17 篇 / 42 chunk（全部已索引） | 活库 MySQL 实计数 |
| `recall@5` | **0.9833**（默认）/ **1.0000**（开重排 N=8/512） | 30 条标注，真实检索端口 + 活库嵌入 |
| `recall@1` / `MRR` | 0.9833 / **1.0000** | 同上 |
| 离题问句 | **返回空结果** | 余弦距离阈值 0.60，按活库实测标定 |
| 红旗拦截率 / 误拦率 | **1.0 / 0.0** | 活库基线 v3：6 条红旗用例**真实跑、真实拦截** |
| 字面判定层覆盖率 | **32%**（1267 条断言中 400 条可判定） | 活库基线 v3 的 20 条真实回答 |

两条必须连着说的取舍：**重排对 `recall@1` 与 `MRR` 零提升**（RRF 融合已把首条命中文档排在第 1 位），只把多标签用例的第二篇拉回 top-5，代价 +1.24 s/次，故默认关闭；**字面判定层只能评估 32% 的断言**，未评估的 867 条里大量是"就医 / 急诊 / 警惕"类安全提示——该层的局限是**覆盖率**而不是准确率，所以它的比率**不作为「幻觉率」对外引用**。

## 界面预览

**患者端**：首页概览 · AI 问诊 · 个人中心

<p align="center">
  <img src="./docs/images/patient-home.png" width="32%" alt="患者首页" />
  <img src="./docs/images/ai-chat.png" width="32%" alt="AI 问诊" />
  <img src="./docs/images/profile.png" width="32%" alt="个人中心" />
</p>

**管理端**：数据概览 · 知识库管理 · 预约管理

<p align="center">
  <img src="./docs/images/admin-dashboard.png" width="32%" alt="管理端数据概览" />
  <img src="./docs/images/knowledge.png" width="32%" alt="知识库管理" />
  <img src="./docs/images/appointments.png" width="32%" alt="预约管理" />
</p>

**公开页**：登录（注册同款布局，登录时可选患者 / 医生 / 管理员）

<p align="center">
  <img src="./docs/images/login.png" width="62%" alt="登录页" />
</p>

> **当前状态：功能已完整落地，并完成一轮检索 / 闭环 / 容错的改造。** TICKET-001…030 实现了五个 Skill 的编排链路、三角色认证与全部业务域（AI 问诊、知识库、图谱、预约与健康档案、人工问诊、文章公告、统计、可观测性与回归基线）；随后的 `agentic-consult` 一票一提交（AC-01…AC-12）补上了**混合检索 + 阈值、检索质量评测、可选本地重排、业务闭环三段、生成侧重试与故障转移、LangChain 生成适配器**，并新增**活库回归基线 v3** 与[指标权威清单](./.scratch/agentic-consult/METRICS.md)。演示数据见 `server/seeds/demo_v1.sql`。下文「架构」描述的是 `SPEC.md` 规定的目标形态，实现与其一致。

## 文档

| 文档 | 内容 |
|---|---|
| [`SPEC.md`](./SPEC.md) | 目标架构规格：问题、目标、约束、seam、接口契约、验收标准、范围外事项。 |
| [`.scratch/agentic-consult/METRICS.md`](./.scratch/agentic-consult/METRICS.md) | **指标的唯一权威清单**：可引用 / 不可引用，每条附口径与出处。引用数字前先看这里。 |
| [`.scratch/agentic-consult/`](./.scratch/agentic-consult/) | 最近一轮改造（AC-01…AC-13）的规格、票据与实测记录，一票一文件。 |
| [`docs/agents/`](./docs/agents/) | 本仓库的工程技能配置：issue tracker、triage 标签、领域文档约定。 |

> 功能层「现状行为」规格（`FUNCTIONAL_SPEC.md`）不随本仓库发布；对外行为以 `SPEC.md` 第 5 章的接口契约与 `contracts/` 为准。

## 架构

Monorepo，前后端分离，无共享代码、无统一构建：

```
.
├── server/          后端：异步 FastAPI + 五 Skill 编排
└── client/          前端：Vue 3 单页应用
```

### AI 链路的五个 Skill

一次问诊的推理被拆成五个边界清晰、契约明确、可独立测试的 Skill（详见 `SPEC.md` 第 4 章）：

| 顺序 | Skill | 类别 | 调用大模型 |
|---|---|---|---|
| 1 | `safety-gate` 安全约束 | Process Rules Skill | 否 |
| 2 | `symptom-normalization` 症状归一化 | 确定性能力 Skill | 否 |
| 3a | `vector-retrieval` 向量检索 | 确定性能力 Skill | 否 |
| 3b | `graph-inference` 图谱推理 | 确定性能力 Skill | 否 |
| 4 | `orchestration` 编排 | 编排 Skill | **是（唯一）** |

单次问诊流程：

```
用户输入
   │
   ▼
[编排 Skill] 生成 trace_id
   │
   ├─▶ ① 安全约束 Skill ── intercept ──▶ 直接返回安全提示（不调用大模型）
   │                     └─ allow ─┐
   ├─▶ ② 症状归一化 Skill            │
   ├─▶ ③ 并行双支路                  │
   │      ├── 向量检索 Skill ──▶ 知识片段 + 引用
   │      └── 图谱推理 Skill ──▶ 候选疾病（coverage 排序）
   ├─▶ ④ 上下文组装（确定性）
   └─▶ ⑤ 大模型流式生成 ──▶ SSE 事件流
                │
                ▼
        trace 落库，可回放
```

要点：安全门在**大模型调用之前**执行且命中即全链路短路；归一化只使用**一份**症状词表；检索与图谱**并行且互不筛选**；每次 Skill 调用与大模型调用都留下可回放的结构化 trace。

### 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python / FastAPI（全异步路由）/ SQLAlchemy 2.0 `AsyncSession` / LangChain（`ChatOpenAI.astream()`）流式调用兼容 OpenAI 的 LLM，嵌入走 httpx 异步调用 |
| 数据 | MySQL（14 个实体）/ Neo4j 异步驱动（医学知识图谱）/ Chroma 本地持久化（向量索引） |
| AI | 兼容 OpenAI 接口的大模型与嵌入服务；检索为 **BM25 + 向量 → RRF 融合 + 距离阈值**，可选**本地 ONNX 交叉编码器重排**（`RERANK_MODEL_DIR`，默认关闭） |
| 前端 | Vue 3 + Vite + Vue Router + Pinia + Element Plus（按需引入），仅通过 RESTful API（含 SSE）通信；图表为自绘内联 SVG，无第三方图表依赖 |

**配置**：连接串、口令与密钥一律经环境变量注入，由 `server/.env` 提供——`core.config.Settings` 读取，样例见 `server/.env.example`。`DATABASE_URL` 必填；缺失时后端启动即报错，不再退回源码里的默认值（TICKET-027）。

**生成适配器**：默认走 LangChain（`LLM_BACKEND=langchain`，对齐 `SPEC.md` §3.1「LangChain 异步调用」）；把 `LLM_BACKEND` 设为 `http` 可退回手写 httpx 的等价实现——两者对同一段内容的增量产出逐字相同，且都保留 `HttpLlmAdapter` 那份异常契约（超时 → 504、不可用 → 503）。备用模型故障转移见 `FALLBACK_LLM_MODEL`。

## 启动方式

后端提供全部业务端点，前端按角色提供各自的视图。

### 前置依赖

- Python 3.11+
- Node.js 18+
- MySQL（`utf8mb4`）与 Neo4j —— 只有跑真实业务时才需要；不启动也能起服务与跑测试
- 大模型/嵌入服务的 API Key

### 后端

```bash
cd server
python -m venv .venv
.venv\Scripts\activate          # Windows；Linux/macOS 用 source .venv/bin/activate
pip install -r requirements-dev.txt   # 含测试依赖；只运行服务可用 requirements.txt

# 配置：复制样例再填写（.env 已被 gitignore）。
# 至少填 DATABASE_URL；需要图谱/令牌/大模型时再补 NEO4J_*、JWT_SECRET_KEY、OPENAI_*。
copy .env.example .env          # Linux/macOS 用 cp .env.example .env

alembic upgrade head            # 建表：应用 Schema 迁移，可重复执行
uvicorn main:app --reload --port 8000
```

接口文档：`http://127.0.0.1:8000/docs`

MySQL 未启动时健康端点不会崩，而是把 `database` 报成 `unavailable`。

### 前端

```bash
cd client
npm install
npm run dev                     # http://localhost:5173
```

开发期由 Vite 代理把 `/api` 与静态资源前缀转发到 `http://127.0.0.1:8000`。

### 初始化数据

需先启动 MySQL 与 Neo4j：

```bash
alembic upgrade head              # 建表：应用 Schema 迁移（见 docs/adr/0001-*.md）

# 演示数据：科室 / 三角色账号 / 预约 / 健康档案 / 人工问诊 / 文章公告 / 会话。
# 只写关系库、不建表，固定编号 9001+ 且可重复执行；向量数据由下一行的脚本负责。
mysql --default-character-set=utf8mb4 -uroot -p medi_sentinel < seeds/demo_v1.sql

python scripts/init_graph.py      # 知识图谱灌数（幂等）
python scripts/init_knowledge.py  # 知识库种子文档灌入并向量化（幂等）
```

演示账号：`patient1` / `doctor1` / `admin1`（患者 / 医生 / 管理员），口令均为
`123456`。Windows 上 `mysql` 客户端必须带 `--default-character-set=utf8mb4`，否则
中文会按本地代码页发送并报 `Incorrect string value`。

种子文档位于 `server/docs_seed/`，由 `init_knowledge.py` 读取；该目录缺失时脚本提示并退出。
图谱查询走 Neo4j **异步驱动**（`AsyncGraphDatabase`，TICKET-013）；向量索引是本地持久化的
Chroma（`server/chroma_db`），嵌入服务经 `OPENAI_API_KEY` 调用。外部服务不可用时脚本给出
明确错误并以非零码退出，服务侧的图谱/检索支路则降级而不阻断问答。

## 测试

```bash
cd server
.venv\Scripts\python.exe -m pytest -q     # 后端

cd ../client
npm test                                  # 前端
```

后端默认连 MySQL，测试则用 SQLite，不需要启动任何外部服务；需要 MySQL 的集成用例在连不上时自动 `skip`。本轮改造完成时的基线：**后端 988 passed + 1 skipped；前端 56 files / 327 passed**。

## 契约

`contracts/` 是前后端共同的事实来源，独立于两侧实现：

- `contracts/openapi.json` —— REST 契约，由应用生成后提交
- `contracts/sse-events.json` —— SSE 帧 Schema（`POST /api/v1/chat/send`）

应用改动后重新生成 REST 契约：

```bash
cd server
.venv\Scripts\python.exe scripts\export_contract.py
```

两侧测试都对着这两份文件校验：后端断言产出满足契约，前端断言能解析契约声明的全部形状；契约与实现不一致时测试会失败。

## 回归基线

行为回归框架（TICKET-023，`SPEC.md` 3.8）的用例集与基线是**版本控制的数据**
（`server/regression/cases/`、`server/regression/baselines/`），随代码一同入库：

```bash
cd server
# 离线录制 / 回放（确定性替身端口，不触碰任何外部依赖）
.venv/Scripts/python.exe scripts/regression.py record --case-set v1 --baseline-version v1
.venv/Scripts/python.exe scripts/regression.py replay --case-set v1 --baseline-version v1

# 活库录制（真实 Neo4j + 活库向量检索 + 真实模型；v3 就是这么来的）
.venv/Scripts/python.exe scripts/regression.py record --case-set v3 --baseline-version v3 --live

# 检索质量：recall@1 / recall@5 / MRR（跑真实检索端口，需要联网）
.venv/Scripts/python.exe scripts/regression.py retrieval-eval --set retrieval-v1

# 字面判定层的四个口径：覆盖率与格式伪影分解（只读，不改判定）
.venv/Scripts/python.exe scripts/regression.py hallucination-calibers --baseline-version v3
```

`replay` 只读基线重建一次问诊并打印 `MetricsReport`，回放期间外部调用次数为 0；
拦截率 < 100% 或误拦率 > 0% 时以非零码退出。同一版本也可经 `POST /regression/runs`
提交、`GET /regression/runs/{run_id}` 轮询。

**三份基线的语义不同，别混用**：`v1` / `v2` 录在**确定性替身端口**上（拦截率等指标是替身
自证）；`v3` 是**真实调用快照**（拦截率 1.0 / 误拦率 0.0 由 6 条红旗用例真实跑出来），
但它不可复现——回放逐字稳定。两个必须知道的读数边界：`diagnosis_drift_rate` 在
**回放路径上是恒真式**（恒 0，代码改坏也报 0），回放也不测量延迟（取基线录制值）。
细节见 [`METRICS.md`](./.scratch/agentic-consult/METRICS.md)。

## 工程约定

- **仓库结构**：Monorepo，`client/` 与 `server/` 两个顶层目录。
- **业务规则**：全部校验、状态语义、权限判定、级联规则都在后端；前端不得复制业务规则作为唯一依据。
- **领域文档**：`docs/adr/`（架构决策记录），人类可读索引入口是根目录 `DECISIONS.md`，见 [`docs/agents/domain.md`](./docs/agents/domain.md)。
- **Issue tracker**：本地 markdown，`.scratch/<feature-slug>/`，见 [`docs/agents/issue-tracker.md`](./docs/agents/issue-tracker.md)。
- **回归基线**：基线用例集与录制结果纳入版本控制，不忽略。

## 范围外

见 `SPEC.md` 第 7 章。凭据与传输加固、数据内容治理、容器化与 CI/CD、历史数据迁移、提示词调优、多租户与国际化等均明确不在本次范围内。
