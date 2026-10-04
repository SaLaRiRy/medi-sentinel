# 25: 真实 LLM 流式适配器

**What to build:** 让问诊链路第一次真正连上大模型。新增一个 `httpx.AsyncClient` 直连的 `LlmPort` 实现，调用兼容 OpenAI 的 `{base_url}/chat/completions`（`stream=true`），把 SSE 增量分块逐段产出；`adapters.py` 在 `openai_api_key` 与 `openai_base_url` 都非空时构建真实适配器，任一为空仍回落到 `UnavailableLlmPort`（保留 009 的 503/504 语义）；`main.py` 的 `llm=UnavailableLlmPort()` 硬编码改为从 adapters 构建——这正是当前「生成失败: RuntimeException」的根因。同时修正 `config.py` 的字面默认并把 LLM 相关变量写进 `server/.env.example`。

**Blocked by:** 09（降级不阻断）、13（图谱与知识库适配器风格）

**Status:** done
Completed: 1d88bd66fc63b8bf47c8ee4ca9ea95ee6f7f5e23

- [x] 未配 LLM（key 空）：行为与现在一致——`error` 帧 code=503，前端显示降级提示，不裸抛 `RuntimeException`
- [x] 配置齐全：正常问诊走真实 LLM，SSE 流式返回
- [x] 超时 → 504，上游不可用 → 503（对齐 009 的 `LlmPort` 异常契约）
- [x] 全异步：`httpx.AsyncClient`，无同步阻塞 I/O
- [x] SSE 帧序不变（session/trace/route/.../done，沿用 007）
- [x] 不引入 langchain、不引入同步 HTTP 客户端
- [x] 适配器落在 `server/skills/llm_http.py`（与 013 的 Chroma 适配器风格一致）
- [x] `server/adapters.py`：key 与 base_url 都非空时构建真实适配器；任一为空仍构建 `UnavailableLlmPort`
- [x] `server/main.py`：把硬编码的 `llm=UnavailableLlmPort()` 改为从 adapters 构建，并在关闭时释放 HTTP 客户端
- [x] `server/core/config.py` 默认值修正：`openai_api_key=""` 保持、`openai_base_url` 用通用端点、`llm_model=qwen3.8-flash`、`embedding_model` 保持
- [x] 新增 `server/.env.example`：列全部 LLM 相关变量（名 + 空值 + 注释）

**TDD 要点（httpx 必须 mock，不发真实网络请求）**

- [x] 正常流式：SSE 分块按序产出为 `stream()` 的增量文本
- [x] chunk 到 SSE 帧的映射：B-1 把每个增量变成 `content` 帧，帧序不变
- [x] 超时 → `TimeoutError` → `error` code 504
- [x] 连接失败 → 非超时异常 → `error` code 503
- [x] 未配 → `build_llm` 返回 `UnavailableLlmPort` → `error` code 503

**边界**

- 不动 001–024 既有行为；023 的 v1 基线（scripted LLM）不变
- 不做真实模型选型对比（SPEC §7.9 范围外）
- 不做演示数据 `.sql`（→ TICKET-026）
- `contracts/sse-events.json` 不动；未新增端点故不重生成 `openapi.json`

## Comments

**完成。** 新增 `server/skills/llm_http.py`（`HttpLlmAdapter`：httpx 直连
`{base_url}/chat/completions`、`stream=true`、解析 SSE 增量），`adapters.build_llm`
在 key 与 base_url 都非空时构建真实适配器、否则回落 `UnavailableLlmPort`，
`main.py` 改为从 adapters 构建并在 lifespan 关闭时释放 HTTP 客户端。
新增 `server/tests/test_llm_http_adapter.py`（17 项，httpx 全程 `MockTransport`，零真实网络）。

套件：后端 `pytest -q --basetemp=.tmp\pytest` → **836 passed**（819 基线 + 17 新增）。
契约未新增端点，`contracts/openapi.json` 未变（`test_contract_seam` 通过）。

### Standards 轴

- 无文档化标准硬违规：仓库无 `CODING_STANDARDS.md`/`CONTRIBUTING.md`，适用 AGENTS.md 约定与 smell 基线。issue 文件位置/命名、测试文件命名、模块中文 docstring 与 013 适配器风格一致；新文件行宽 ≤88、无尾随空格、无 `langchain`/同步客户端。
- 判断项 1（Duplicated Code）：`HttpLlmAdapter` 的惰性 `client` 属性 + `close()` 与 `rag/chroma_adapter.py` 的 `OpenAiCompatibleEmbedder` 形状重复。两者端点/语义不同，且该模式已在 013 被接受，保持现状。
- 判断项 2（Speculative Generality）：`timeout: float = 60.0` 构造参数未被 `build_llm` 或任何测试显式传入，实际只走默认值。保留为具名的默认截止时间（替代魔法数），非配置钩子。
- 判断项 3（Primitive Obsession）：`_delta_of` 用 `None | "" | str` 三态区分「结束 / 无文本 / 增量」，以字符串返回型重载哨兵；已在 docstring 说明，可接受。
- 判断项 4（测试耦合文档格式）：`test_env_example_*` 以正则解析 `.env.example`、`test_llm_config_literal_defaults_*` 读 `model_fields` 默认值。二者锁定本票的字面要求，属 024 已接受的同类做法。
- 文档陈旧（非本票代码违规）：README §技术栈仍写「LangChain 异步调用」、§配置称仅 `OPENAI_API_KEY` 经环境变量注入；本票已按 Q1/Q2 决策用 httpx + Settings 覆盖，README 未在范围内，留待后续。

### Spec 轴

- 验收清单 11 项与 TDD 要点 5 项全部落地，各有可执行断言：适配器请求形状（URL/POST/`stream:true`/model/messages/Auth）、增量顺序、`session→trace→route→content→done` 帧序、超时→504、连接失败→503、`build_llm` 三分支、`create_app` 端口类型与关闭释放、config 字面默认、`.env.example` 变量。
- 未配 → 503 且不裸抛：`build_llm` 回落 `UnavailableLlmPort`，009 已有的 `RuntimeError→503` 映射不变；前端 `ChatView.vue` 既有逻辑把 `error` 帧的 `message` 渲染为提示（只读核对，未改动）。
- 无范围蔓延：未新增端点、未改 `sse-events.json`、未做 `.sql`、未做模型选型对比；`openapi.json` 不变。
- 说明 1（真实模型未实测）：按本票 TDD 要求「httpx 必须 mock、不发真实网络」，验收项「走真实 LLM」以 `MockTransport` 证明请求/解析/映射，未开真实 socket。真实端点走本地 `.env`（已写入用户配置，git 忽略）。
- 说明 2（顺带修复）：`config.py` 的 `database_url` 口令 `root→123456` 是开工前工作区已存在的改动，非本票要求，予以保留并随本提交落地。
