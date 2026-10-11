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

**Status:** done
Completed: db9eba7

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

**完成（2026-10-11）。** 检索从「纯向量单路、无阈值」改成「向量 + BM25 → RRF 融合 → 两道门」。

### 交付

| 文件 | 变更 |
|---|---|
| `server/rag/hybrid.py`（新增） | `HybridRetriever`（同时满足 `RetrievalPort` 与 `VectorStore`）、`tokenize`（中文二字组切分）、`rrf_fuse`（纯函数） |
| `server/rag/chroma_adapter.py` | 新增 `all_documents()`（BM25 语料来源） |
| `server/adapters.py` | `build_vector_store` 装配 `HybridRetriever`（唯一装配点） |
| `server/regression/divergences.py` | 正则 `^(A|H|S)-\d+$`、`STACK_SCOPE`、`stack_ids()` |
| `.scratch/medisentinel/intentional-divergences.md` | 新增 `stack` 子集 + `S-1` |
| `server/requirements.txt` | `rank_bm25>=0.2`（实测 `rank_bm25-0.2.2` 已装） |
| `vector_retrieval/{SKILL.md,retrieval.py}`、`orchestration/skill.py` | 注释与文档跟实现对齐（「互不重排」的旧说法已改） |
| 顺带修 | `skills/protocol.py` 补 `BaseException` 分支写 `cancelled` span；`orchestration/skill.py` 取消时也写 orchestration span |

### 票内决策（用户授权「选推荐值」）

1. **融合写在端口实现层内部**——端口签名与调用序列不变，`regression/ports.py`、
   `tests/doubles.py`、`baseline` 全部零改动，回放不破（spec.md 4.4 的首选做法）。
2. **BM25 语料来源改为 Chroma 集合的全量分块**（`all_documents()`），而非票面写的
   `t_knowledge_chunk` 表：两者由同一次 `split_text` 写入、内容天然一致，且这样
   `rag/` 不必引入关系库依赖、`build_vector_store(settings)` 的签名也不用动。
   `collection.get()` 是本地 SQLite 读取，**不触发嵌入服务**。
3. **两道门**：`MAX_VECTOR_DISTANCE`（向量距离上限，超过者不进融合，仍可由 BM25 带入）
   + `RETRIEVAL_MIN_SCORE = 1/(60+10)`（RRF 分下限＝「至少在某一路排进前 10 名」）。
   候选深度 `CANDIDATE_K = 20` 比输出 `top_k = 5` 深，阈值才有意义。

### 实测标定（活库 42 chunk；`server/.tmp/` 一次性脚本，跑完即删）

```
相关问句最佳距离: 0.252 / 0.286 / 0.286 / 0.288 / 0.311 / 0.315 / 0.343
相关问句 top20 尾部: 到 0.685
离题问句「今天天气怎么样」: 0.699 起
离题问句「股票怎么开户」:   0.769 起
```

→ 取 `MAX_VECTOR_DISTANCE = 0.60`：把离题命中全部挡在门外。相关侧 0.61–0.685 的尾部
也一并丢弃，但它们不在融合后的前 10 名里，对 top-5 输出无影响。
**离题问句现在返回空结果**（原来是恒 5 条垃圾、且全部进提示词）：
`今天天气怎么样 → []`、`股票怎么开户 → []`；7 条医学问句仍各返回 5 条、来源 ≥2 篇。

⚠️ **余量提示**：离题侧最低 0.699，相关侧尾部到 0.685——0.60 这个阈值离**相关侧的尾部**
很近（留了 0.085 的余量），若将来换嵌入模型或扩语料，必须重新标定这一行，
不要直接沿用。

### 已知局限（留给票 04，不在此票硬修）

BM25 会被公共二字词带进噪声：`高血压吃什么药` 的第 5 条是 `中暑的识别与急救.md`
（只因共享「什么」），BM25 分 2.40。**IDF 卡不掉**——42 篇语料里 `什么` 的 IDF 反而是
2.42（在这个小语料里算"稀有词"）。字面巧合与真命中靠阈值分不开，
这正是票 04 本地重排要解决的事。

### TDD

`server/tests/test_hybrid_retrieval.py` 13 项（分词 3 / RRF 3 / 两道门 4 / 降级与写路径 3），
全部用假 store，不碰 Chroma、嵌入与网络。另有 `test_regression_divergences.py` 的
`stack` 子集断言、`test_skill_protocol.py` 与 `test_stream_lifecycle.py` 的取消 span 断言。

实现过程中踩到并修掉的两个真问题：

1. BM25 小语料下 IDF 可能整体为负，用「分数 > 0」当门会把整库滤空 → 改成
   「与问句有词面重叠才算命中」。
2. `_bm25_rank` 先切片后过滤会让名次越界 → 先筛候选再取前 `depth`。

### 套件

后端 `pytest -q --basetemp=.tmp\pytest` → **873 passed**（857 + 16 新增，225 s）。
前端未改动，未重跑。

### divergence

`S-1`（scope `stack`）已登记；`ai_chain_ids()` / `http_contract_ids()` 输出不变。
