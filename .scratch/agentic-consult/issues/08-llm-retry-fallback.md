# 08: 降级容错 —— 超时重试 + 备用模型故障转移

**What to build:** 全仓 `retry` / `backoff` / `tenacity` **零实现**（4 处命中全是注释）。
本票两环 + 一处死配置修复。

## 环 1 —— 超时重试

- 落点：`server/skills/llm_http.py` 的 `stream()` 内，**不放 orchestrator**。
- 仅对**连接错误与首字节前超时**重试；指数退避；总预算硬上限（建议 2 次 / < 10 s）。
- 🔴 **硬约束：一旦已推出 `content` 帧，禁止重试**。`server/skills/orchestration/skill.py:287-291`
  是边收边推（`yield {"type": "content", …}`），重试会让前端看到**拼接内容**。
  实现上：`stream()` 只有在**尚未 yield 任何 chunk** 时才允许重开连接。
- 错误契约**不变**：重试耗尽仍翻成 `TimeoutError` → 504
  （`server/skills/llm_http.py:64-67`，TICKET-009/025 锁死）。

## 环 2 —— 备用模型故障转移

- 配置：`server/core/config.py` 加 `fallback_llm_model: str = ""`（空则禁用）。
- 实现：包一层 `LlmPort`（主/备二者），主失败且**未吐字** → 切备。
  装配点是唯一入口 `server/adapters.py:40-53 build_llm`。
- **必须改 `SPEC.md:398`**：把「大模型生成不可用**无法降级**」重新表述为
  **「故障转移（切换执行单元，生成能力不降级）」**，否则会被判为回归。
  代码三处重申同一原则，必须一起改：`server/skills/ports.py:35`、`skill.py:12-13`、`skill.py:60`。

## 顺带修死配置

`server/core/config.py:44-46` 的 `chunk_size` / `chunk_overlap` / `retrieval_top_k`
**生产路径从不读**（真正生效的是 `rag/chunking.py:19-20` 模块常量与
`vector_retrieval/retrieval.py:13` 的 `RETRIEVAL_TOP_K`）。要么让生产路径读 Settings，
要么删掉这些字段；**不要让「配置了但不生效」留在库里**（面试会被追问）。

## 已删除（**不要实现**）

原「**本地向量库兜底**」：语义不成立（向量库是上下文支路，不是生成的替代；生成失败仍只能
503/504），且冲突 `SPEC.md:398`。

**Blocked by:** 无

**Status:** ready-for-agent

## 验收清单

- [ ] `httpx.MockTransport`：前两次连接失败、第三次成功 → 只出现**一次**完整流，无重复内容
- [ ] **已吐字后中断 → 不重试**：断言 `content` 帧序列无重复前缀，错误仍翻 503/504
- [ ] 退避与总预算可断言（注入可替换的 sleep，不进真实等待）
- [ ] 主模型失败且未吐字 → 备模型接管，`error` 帧**不出现**，`done` 帧正常
- [ ] 主备都失败 → 仍 504 / 503，帧序 `session→trace→route→…` 不变
- [ ] `fallback_llm_model=""` 时行为与现在**完全一致**（既有 `test_llm_http_adapter.py` 全绿）
- [ ] `SPEC.md:398` 措辞更新，代码三处 docstring 同步
- [ ] 死配置已修或已删，且有断言钉住（配置项与实际生效值一致）
- [ ] divergence 登记：`S-4` / scope **`stack`**（改 `SPEC.md:398` 措辞属生成策略变更，
      记录即可，**不**扩大 `ai-chain` 豁免分母）

## TDD 要点

- 重试次数：注入计数器端口，断言 ≤ 上限。
- 首字节前 vs 首字节后：两条用例覆盖「允许重试」「禁止重试」的分界。
- 故障转移：主端口抛连接错 → 备端口被调用一次；主端口中途断流 → 备端口**不**被调用。
- 错误映射：`TimeoutError` → 504、其他 → 503（复用 025 的既有断言）。

## 边界与坑

- 重试**不能**放大上游计费：只在连接建立阶段重试，不重发已生成的 token。
- 备用模型走**同一 API key 换模型名**（已定决定），不要引入第二套凭据。
- 帧序不变量（`SPEC.md` §5.5 六条）在任何失败路径下都成立。

## Comments
