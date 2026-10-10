# 01: 扩知识库至 ≥30 chunk（地基）

**What to build:** 活库实测 `t_knowledge_file = 3`、**`t_knowledge_chunk = 3`**，而
`RETRIEVAL_TOP_K = 5`（`server/skills/vector_retrieval/retrieval.py:13`）——检索池只有 3 条时
**recall@5 恒等于 100%**，票 03 的评测数字是废话。本票把知识库扩到 **≥30 chunk / ≥10 篇**：
在 `server/docs_seed/` 新增中文医学知识文档，走 `server/scripts/init_knowledge.py`
（按文件名幂等跳过，`scripts/init_knowledge.py:87-92`）灌入并向量化到状态 2。
**不改任何生产代码。**

**Blocked by:** 无（第一票）

**Status:** ready-for-agent

## 交付物

1. `server/docs_seed/*.md` 新增 **≥10 篇**，每篇一个主题（避免互相包含），覆盖至少：
   发热/流感、高血压、糖尿病、急性胃肠炎、偏头痛、过敏性鼻炎、支气管哮喘、失眠、
   缺铁性贫血、颈椎病、痛风、湿疹/荨麻疹、儿童发热护理、脂肪肝、高血脂。
2. 每篇 **500–2000 字**、UTF-8、带 `##` 小节标题，含可被单一 query 命中的要点句
   （症状描述、常用药名、检查项、就医指征），文末一行「资料来源：……」标注为科普改写。
   （500 字 ≈ 1 chunk、2000 字 ≈ 4–5 chunk；10–15 篇即越过 30 chunk。）
3. 新增 `server/tests/test_seed_corpus.py`：**纯离线**文件级断言（不碰 DB / 网络 / 嵌入）——
   篇数 ≥10、每篇 ≥500 字、非空、无重复文件名、可 UTF-8 解码。

## 验收清单

- [ ] `t_knowledge_file >= 13`（原 3 + 新增 ≥10），`t_knowledge_chunk >= 30`（活库 `SELECT COUNT(*)`）
- [ ] 新增文件 `vector_status = 2`（已索引），**无 3**（失败）
- [ ] 脚本自校验通过：每个文件的分块数 == 该 file_id 的向量条目数
      （`scripts/init_knowledge.py:113-117` 的同一致性断言）
- [ ] 只读抽查：≥5 个不同 query 经 `ChatVectorStore.search` 各返回 ≥3 条，且来源不只 1 篇
- [ ] `git diff --stat` 只出现 `server/docs_seed/*.md` 与新增测试文件，无生产代码改动
- [ ] `pytest server/tests/test_seed_corpus.py` 绿

## TDD 要点

- 先写 `test_seed_corpus.py` 并跑红（当前 `docs_seed/` 只有 3 篇，`>=10` 必红），再补文档转绿。
- 灌库本身**不可自动化**（需 MySQL + 嵌入服务），以脚本输出 + SQL 计数 + 抽查为证据，贴进 Comments。

## 边界与坑

- `.env` 是相对路径（`server/core/config.py:11` `env_file=".env"`）→ **必须在 `server\` 下运行**，
  否则 `database_url` 为空、连接全失败。
- 嵌入走 `openai_base_url`（DashScope 兼容端点）→ **需要网络**；单篇失败会把整篇置 3，
  重跑时前 3 篇按文件名跳过、新增篇重试。
- 幂等键是**文件名**：改了文件名会重复入库（生成新 file_id 与重复向量）。
- 顺手清理 Neo4j 里混入英文的疾病节点 `慢性 daily 头痛`（可选，登记在 Comments）。
- 敏感信息：`server/.env` 含真实 key，**不要把值写进票据、日志或提交**。

## Comments
