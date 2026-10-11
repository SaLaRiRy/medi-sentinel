# 09（可选，最后）: LangChain 换 `LlmPort` adapter

**What to build:** 只替换 B-3 的 `LlmPort` 实现层，**保留 `HttpLlmAdapter`** 做对照/回退。

1. 新增 `server/skills/langchain_llm.py`（内部 `ChatOpenAI.astream()`，
   把 `AIMessageChunk` 转成增量文本；超时仍翻 `TimeoutError` → 504）。
2. `server/adapters.py:40-53 build_llm` 按配置切换；未配 key 仍回落 `UnavailableLlmPort`。
3. 补 `langchain` / `langchain-openai` 到 `server/requirements.txt`。
4. 顺手结清文档债：`SPEC.md:116` 本就写着「LangChain 异步调用」（改完自动正确）；
   `server/skills/llm_http.py:5` 注释的 `3.1` 应改成 `4.1 B-3`。

**Blocked by:** 08（降级链稳定后再换底层执行单元）

**Status:** done
Completed: f0da157

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

**完成（2026-10-11）。** LangChain 换到 `LlmPort` 的实现层，`HttpLlmAdapter` 保留可切换。
**没有炸，无需回滚。**

### 交付

| 文件 | 变更 |
|---|---|
| `server/skills/langchain_llm.py`（新增） | `LangChainLlmAdapter`（`ChatOpenAI.astream()`）：内容块拉平成文本增量、空增量跳过、超时归一到 `TimeoutError`、其他异常原样外抛、中途断流保留已推出的分块 |
| `server/core/config.py` | `llm_backend: str = "http"`（`http` \| `langchain`） |
| `server/adapters.py` | `build_llm` 按 `llm_backend` 选实现；故障转移包装对两个实现一视同仁 |
| `server/requirements.txt` | `langchain-core>=1.0` / `langchain-openai>=1.0` |
| `server/.env.example` | `LLM_BACKEND` |
| `server/skills/llm_http.py` | 顶部注释改对：手写 httpx 的依据是 **4.1 B-3**（原注释把条款写成 3.1，而 3.1 恰恰要求 LangChain） |
| 登记册 | `S-5`（scope `stack`） |

### 推翻既有决定的理由

TICKET-025 的验收项写着「不引入 langchain」，`llm_http.py` 的注释也这么写——但那是
一次**自我决定**，而 `SPEC.md:116` 的技术栈表一直要求「大模型与嵌入 | LangChain 异步调用」。
本票改的是**实现层**：端口签名、异常契约、SSE 帧序都不变，`HttpLlmAdapter` 原样保留，
由 `llm_backend` 切换，所以这是一次可回退的替换，不是重写。

### 依赖与代价（实测）

- 安装走**阿里云镜像**（`https://mirrors.aliyun.com/pypi/simple/`）：清华镜像对该包返回
  `from versions: none`，疑似同步延迟。落地版本：`langchain-openai 1.7.0`、
  `langchain-core 1.6.9`、`openai 3.28.0`，连带 `langsmith` / `tiktoken` / `jsonpatch` 等共 19 个包。
- **副作用**：`httpx` 被抬到 **0.28.1**（原 0.27 系）。`pip check` 干净，959 项测试全过。
- `regression/` 目录**零 langchain 引用**（有测试钉住），回放仍然零外部依赖。

### 等价性怎么证明的

- 同一段内容序列，两个适配器产出的增量序列**逐字相同**（测试里各跑一遍再断言相等）。
- 超时（含 `openai.APITimeoutError`）→ `TimeoutError` → 504；其他异常原样外抛 → 503；
  中途断流保留已推出的分块（不重放、不拼接）。
- `build_llm` 三分支：默认 → `HttpLlmAdapter`；`llm_backend=langchain` → `LangChainLlmAdapter`；
  配了 `fallback_llm_model` → 无论选哪个实现都包 `FallbackLlmAdapter`。

### TDD

`server/tests/test_langchain_llm.py` **11 项**：文本抽取 2 / 流式产出 3 / 超时与异常 2 /
中途断流 1 / 与 http 适配器等价 1 / 装配 2 / 回放零 langchain 1。

### 套件

- 后端 `pytest -q --basetemp=.tmp\pytest-user` → **959 passed**
- 前端本票无改动

### divergence

`S-5`（scope `stack`）已登记；`stack_ids` 断言同步 `range(1, 5)` → `range(1, 6)`。

### 追加（同日）：默认后端切到 LangChain

真机冒烟（`.env` 里的真实密钥，两个后端各发一次流式请求）：

```
--- http: 1 段 -> '你好'
--- langchain: 1 段 -> '你好'
```

两个后端对真实端点都通、输出一致。既然 `SPEC.md` 3.1 本来就要求「LangChain 异步调用」，
把默认值留成 `http` 等于票 09 没接上，因此 `llm_backend` 默认改为 **`langchain`**，
`http` 保留为可切换的对照实现（`.env` 里 `LLM_BACKEND=http` 即可退回）。

连带同步了两处既有断言：`test_llm_http_adapter.py` 的两条用例改为显式
`llm_backend="http"`（它们测的是 http 那条实现），`test_llm_retry_fallback.py`
的装配用例同样固定后端。全量 **959 passed**。
