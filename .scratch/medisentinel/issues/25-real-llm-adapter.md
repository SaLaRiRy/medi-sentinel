# 25: 真实 LLM 流式适配器

**What to build:** 让问诊链路第一次真正连上大模型。新增一个 `httpx.AsyncClient` 直连的 `LlmPort` 实现，调用兼容 OpenAI 的 `{base_url}/chat/completions`（`stream=true`），把 SSE 增量分块逐段产出；`adapters.py` 在 `openai_api_key` 与 `openai_base_url` 都非空时构建真实适配器，任一为空仍回落到 `UnavailableLlmPort`（保留 009 的 503/504 语义）；`main.py` 的 `llm=UnavailableLlmPort()` 硬编码改为从 adapters 构建——这正是当前「生成失败: RuntimeException」的根因。同时修正 `config.py` 的字面默认并把 LLM 相关变量写进 `server/.env.example`。

**Blocked by:** 09（降级不阻断）、13（图谱与知识库适配器风格）

**Status:** ready-for-agent

- [ ] 未配 LLM（key 空）：行为与现在一致——`error` 帧 code=503，前端显示降级提示，不裸抛 `RuntimeException`
- [ ] 配置齐全：正常问诊走真实 LLM，SSE 流式返回
- [ ] 超时 → 504，上游不可用 → 503（对齐 009 的 `LlmPort` 异常契约）
- [ ] 全异步：`httpx.AsyncClient`，无同步阻塞 I/O
- [ ] SSE 帧序不变（session/trace/route/.../done，沿用 007）
- [ ] 不引入 langchain、不引入同步 HTTP 客户端
- [ ] 适配器落在 `server/skills/llm_http.py`（与 013 的 Chroma 适配器风格一致）
- [ ] `server/adapters.py`：key 与 base_url 都非空时构建真实适配器；任一为空仍构建 `UnavailableLlmPort`
- [ ] `server/main.py`：把硬编码的 `llm=UnavailableLlmPort()` 改为从 adapters 构建，并在关闭时释放 HTTP 客户端
- [ ] `server/core/config.py` 默认值修正：`openai_api_key=""` 保持、`openai_base_url` 用通用端点、`llm_model=qwen3.8-flash`、`embedding_model` 保持
- [ ] 新增 `server/.env.example`：列全部 LLM 相关变量（名 + 空值 + 注释）

**TDD 要点（httpx 必须 mock，不发真实网络请求）**

- [ ] 正常流式：SSE 分块按序产出为 `stream()` 的增量文本
- [ ] chunk 到 SSE 帧的映射：B-1 把每个增量变成 `content` 帧，帧序不变
- [ ] 超时 → `TimeoutError` → `error` code 504
- [ ] 连接失败 → 非超时异常 → `error` code 503
- [ ] 未配 → `build_llm` 返回 `UnavailableLlmPort` → `error` code 503

**边界**

- 不动 001–024 既有行为；023 的 v1 基线（scripted LLM）不变
- 不做真实模型选型对比（SPEC §7.9 范围外）
- 不做演示数据 `.sql`（→ TICKET-026）
- `contracts/sse-events.json` 不动；未新增端点故不重生成 `openapi.json`
