# MediSentinel

AI 智能医疗问诊平台 —— 异步、Skill 化重建。

> **当前状态：骨架阶段。** TICKET-001 已落地 monorepo 骨架、契约 seam（B-1…B-5、F-1…F-3、C-1）与 Alembic 迁移；目前只有 `/api/v1/health` 一个端点，五个 Skill 与各业务域尚未实现。下文「架构」描述的是 `SPEC.md` 规定的目标形态。

## 文档

| 文档 | 内容 |
|---|---|
| [`FUNCTIONAL_SPEC.md`](./FUNCTIONAL_SPEC.md) | 参考实现的**现状行为**规格：14 个实体、73 个 HTTP 端点、RAG 与图谱链路的实际行为，含附录 A 术语表与附录 B 现状边界。它是功能对等的基线，不是改造建议。 |
| [`SPEC.md`](./SPEC.md) | 目标架构规格：问题、目标、约束、seam、接口契约、验收标准、范围外事项。 |
| [`docs/agents/`](./docs/agents/) | 本仓库的工程技能配置：issue tracker、triage 标签、领域文档约定。 |

领域概念一律以 `FUNCTIONAL_SPEC.md` 附录 A 的术语表为准。

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
| 后端 | Python / FastAPI（全异步路由）/ SQLAlchemy 2.0 `AsyncSession` / LangChain 异步调用 |
| 数据 | MySQL（14 个实体）/ Neo4j 异步驱动（医学知识图谱）/ Chroma 本地持久化（向量索引） |
| AI | 兼容 OpenAI 接口的大模型与嵌入服务 |
| 前端 | Vue 3 + Vite + Vue Router + Pinia + Element Plus + ECharts + axios，仅通过 RESTful API（含 SSE）通信 |

**配置**：除大模型密钥经环境变量 `OPENAI_API_KEY` 注入外，其余连接参数均为源码常量（`FUNCTIONAL_SPEC.md` 附录 B.2 记录的现状，`SPEC.md` 第 7.1 节明确保持原样）。

## 启动方式

后端骨架与前端外壳已可启动；五个 Skill 与业务域尚未实现，界面目前展示后端健康状态。

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

alembic upgrade head            # 建表：应用 Schema 迁移，可重复执行
set OPENAI_API_KEY=<your-key>   # Windows；Linux/macOS 用 export OPENAI_API_KEY=<your-key>
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
python scripts/init_graph.py      # 知识图谱灌数（幂等）
python scripts/init_knowledge.py  # 知识库种子文档灌入并向量化（幂等）
```

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

后端默认连 MySQL，测试则用 SQLite，不需要启动任何外部服务。

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

行为回归框架（TICKET-023，`SPEC.md` 3.8）由两条命令驱动；用例集与基线是版本控制
的数据（`server/regression/cases/`、`server/regression/baselines/`），随代码一同入库：

```bash
cd server
.venv\Scripts\python.exe scripts\regression.py record --case-set v1 --baseline-version v1
.venv\Scripts\python.exe scripts\regression.py replay --case-set v1 --baseline-version v1
```

`record` 用确定性端口离线录制基线（不触碰图库、向量索引、嵌入服务与大模型）；
`replay` 只读基线重建一次问诊并打印 `MetricsReport`（红旗拦截率、误拦率、诊断漂移率、
幻觉率与按 `intercepted`/`llm`/`degraded` 分组的 P95 延迟），回放期间外部调用次数为 0。
拦截率 < 100% 或误拦率 > 0% 时以非零码退出。同一版本也可经 `POST /regression/runs`
提交、`GET /regression/runs/{run_id}` 轮询。

## 工程约定

- **仓库结构**：Monorepo，`client/` 与 `server/` 两个顶层目录。
- **业务规则**：全部校验、状态语义、权限判定、级联规则都在后端；前端不得复制业务规则作为唯一依据。
- **领域文档**：`GLOSSARY.md` 与 `docs/adr/`；ADR 的人类可读索引入口是根目录 `DECISIONS.md`，见 [`docs/agents/domain.md`](./docs/agents/domain.md)。
- **Issue tracker**：本地 markdown，`.scratch/<feature-slug>/`，见 [`docs/agents/issue-tracker.md`](./docs/agents/issue-tracker.md)。
- **回归基线**：基线用例集与录制结果纳入版本控制，不忽略。

## 范围外

见 `SPEC.md` 第 7 章。凭据与传输加固、数据内容治理、容器化与 CI/CD、历史数据迁移、提示词调优、多租户与国际化等均明确不在本次范围内。
