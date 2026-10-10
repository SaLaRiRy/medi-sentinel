# 02: 混合检索（BM25 + 向量）+ RRF 融合 + 相似度阈值

**What to build:** 现在检索只有向量一条路（`server/rag/chroma_adapter.py:118-133`
`ChromaVectorStore.search`），且 `server/skills/vector_retrieval/retrieval.py:43-44` 明写
「**无最低命中阈值**——距离再大的命中也照常保留」。本票把它改成
**BM25 + 向量 → RRF 融合 → 阈值过滤**：

1. 新增 `server/rag/hybrid.py`：`HybridRetriever` 包住向量 store 与 BM25 索引，
   实现 B-3 的 `RetrievalPort.search`（`server/skills/ports.py:25-27`，签名**不变**）。
2. 融合用 **RRF**（Reciprocal Rank Fusion，`k=60`）——只用排名，避免余弦距离与
   BM25 分数不可比。
3. 阈值：RRF 分数低于 `RETRIEVAL_MIN_SCORE` 的命中丢弃；常量写进
   `vector_retrieval/SKILL.md` 的「边界情况」节。
4. BM25 语料来源：**`t_knowledge_chunk` 分块表**——懒构建内存索引，
   不引第二个持久化库。
5. 依赖：`rank_bm25`（纯 Python、无模型、无网络）**必须显式补进 `server/requirements.txt`**
   （现在只有 14 行，没有它）。
6. **必须同步改注释**：`server/skills/orchestration/skill.py:240-242` 写着
   「neither one filters or **re-ranks** the other」，加 RRF 后失真 —— 改成
   「两路各自独立产出；融合发生在检索端口内部，图谱支路不参与」。

**Blocked by:** 01（池子要先够大才有排序可言）

**Status:** ready-for-agent

## 第一件事：登记册解析器支持 `stack` 族（否则本票起的 `S-*` 全是空转）

`server/regression/divergences.py:19` 的正则现在是 `^(A|H)-\d+$`，`S-*` 条目会被
`parse_registry` **静默丢弃**。本票先落这三处改动，再登记 `S-1`：

1. 正则扩成 `^(A|H|S)-\d+$`；
2. 新增 `STACK_SCOPE = "stack"` 与 `stack_ids(divergences)`（与 `ai_chain_ids` /
   `http_contract_ids` 并列，同样按 scope 过滤）；模块 docstring 写清
   **族 ↔ scope 一一对应**（`A`=ai-chain / `H`=http-contract / `S`=stack）；
3. `.scratch/medisentinel/intentional-divergences.md` 新增 `stack` 子集小节并登记 `S-1`
   （本票的「RRF 融合 + 阈值」属**框架级检索变更**）。

⚠️ **`stack` 条目不进 `exempt_divergences`、也不进 `recorded_divergences`**——
`Baseline` 的这两个列表保持原样；塞进 `ai-chain` 会扩大漂移/幻觉豁免分母，
让门禁对本次改动失明（spec.md 4.6）。

## 顺带修：取消分支的 span 缺口（独立于本票主线，可先行单独一个 commit）

`server/skills/protocol.py:66` 用 `except Exception` 兜底，捕不到 `CancelledError` /
`GeneratorExit`（都是 `BaseException`）→ **被取消的分支 Skill 一条 span 都不留**；
`Skill._record` 的 `status` 已经声明接受 `"cancelled"`（`protocol.py:88`），
但全项目无调用点传它。修法：`Skill.invoke` 补 `BaseException` 分支，写一条
`status="cancelled"` 的 span 后再抛出（与 `orchestration/skill.py:314` 的既有写法对齐），
并对齐 `orchestration` 自身在取消时的 span 行为。本票之后再引入新阶段时，
这个洞会从设计瑕疵变成真 bug。

## 关键设计约束

- **融合必须在 `RetrievalPort` 实现层内部完成**，**不得**让编排层多调一次端口。
  回放是纯 FIFO 游标（`server/regression/ports.py:104-106`、`:134-135`），
  端口调用次数一变，`baseline` 的录制序列与 `ReplayRetrievalPort` 全部错位（spec.md 4.4）。
- 向量库不可用时**仍要 `degraded: ["retrieval"]`**，不得抛错（`SPEC.md:398`）：
  BM25 单独可用不算替代——检索是增强支路，两条子路都不可用才降级。

## 验收清单

- [ ] 同一 query 下混合结果**包含 BM25 独有命中**（构造一个只被 BM25 召回的用例）
- [ ] 阈值生效：低于阈值的命中被丢弃（构造低分样本）
- [ ] `degraded` 语义不变：向量库不可用 → `done.degraded == ["retrieval"]`，不产生错误码
- [ ] **回放不破**：`pytest server/tests/test_regression_record_replay.py` 全绿
- [ ] `RetrievalPort` 协议不变（`@runtime_checkable`，`server/tests/test_ports.py` 绿）
- [ ] `rank_bm25` 进 `requirements.txt`，且 **venv 里已实际可导入**（实测记录贴 Comments）
- [ ] `skill.py:240-242` 注释已改，与新行为一致
- [ ] `vector_retrieval/SKILL.md` 四节与实现一致（端到端句含 RRF 与阈值）
- [ ] `divergences.py` 能解析 `S-*`；`stack_ids()` 返回 `["S-1"]`；
      `ai_chain_ids()` / `http_contract_ids()` 输出**不变**（`A-1…A-7` / `H-1…H-12`）
- [ ] `S-1` 已登记在 `intentional-divergences.md` 的 `stack` 子集
- [ ] 顺带修：取消分支写 `cancelled` span，测试覆盖「取消后 span 不丢」

## TDD 要点

- RRF 纯函数：给定两组排名列表 → 手算期望融合序（不进数据库、不调嵌入）。
- 阈值：低于阈值被丢、等于阈值保留（边界）。
- BM25 独有命中被召回：`FakeVectorStore` 只返回 1 条、BM25 语料返回另一条 → 结果含两条。
- 降级：向量 store 抛错 → 端口仍返回结果（或标记降级），不向外抛。
- 依赖登记：正则解析 `requirements.txt` 断言含 `rank_bm25`（沿用 025 的 `.env.example` 类做法）。

## 边界与坑

- `rank_bm25` 的中文分词：BM25 需要 **token 序列**。中文无空格 → 必须显式选一种切分
  （建议 bigram 字符切分或复用症状词表 + 正则），**不要**默认 `str.split()`；
  切分方式要写进 `SKILL.md` 并在测试里钉住。
- BM25 索引是进程内状态：知识库增删后必须失效重建，否则索引陈旧（票内给出失效时机）。

## Comments
