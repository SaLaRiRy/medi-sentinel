# 09（可选，最后）: LangChain 换 `LlmPort` adapter

**What to build:** 只替换 B-3 的 `LlmPort` 实现层，**保留 `HttpLlmAdapter`** 做对照/回退。

1. 新增 `server/skills/langchain_llm.py`（内部 `ChatOpenAI.astream()`，
   把 `AIMessageChunk` 转成增量文本；超时仍翻 `TimeoutError` → 504）。
2. `server/adapters.py:40-53 build_llm` 按配置切换；未配 key 仍回落 `UnavailableLlmPort`。
3. 补 `langchain` / `langchain-openai` 到 `server/requirements.txt`。
4. 顺手结清文档债：`SPEC.md:116` 本就写着「LangChain 异步调用」（改完自动正确）；
   `server/skills/llm_http.py:5` 注释的 `3.1` 应改成 `4.1 B-3`。

**Blocked by:** 08（降级链稳定后再换底层执行单元）

**Status:** ready-for-agent

## 必须写进票内的决策理由

本票**推翻** `server/skills/llm_http.py:5` 的「不引入 langchain」与
TICKET-025 的验收项「不引入 langchain」——那是一次自我决定，而 `SPEC.md:116`
的权威表述一直要求 LangChain。票内要写明：改的是**实现层**，端口契约与
`error` 帧语义不变，且 `HttpLlmAdapter` 保留可切换。

## 验收清单

- [ ] `build_llm` 三分支：key 空 → `UnavailableLlmPort`；配 LangChain → 新 adapter；
      未配 → `HttpLlmAdapter`（既有行为不变）
- [ ] 流式增量顺序与 `HttpLlmAdapter` 等价（同一份假 SSE 喂两个 adapter，逐段相等）
- [ ] 超时 → 504、连接失败 → 503；未配 → 503，帧序不变
- [ ] `langchain` / `langchain-openai` 进 `requirements.txt`
- [ ] `server/regression/ports.py` **不得 import langchain**（AST 测试仍绿）
- [ ] 既有 `test_llm_http_adapter.py` 全绿（`HttpLlmAdapter` 未被替换掉）
- [ ] divergence 登记；`SPEC.md` 无需改动（116 行本就正确）

## 边界与坑

- 收益最低，**可随时砍**；若时间不够，本票直接置 `wontfix` 并在 spec.md 记一笔。
- 新增依赖会拉大安装体积；`requirements.txt` 只加必要两项。

## Comments
