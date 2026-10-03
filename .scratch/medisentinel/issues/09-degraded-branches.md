# 09: 降级不阻断

**What to build:** 增强支路不可用时的降级语义：图谱或向量索引挂掉时，问答照常完成，结束帧标出哪条支路降级，而不是整条链路失败。这让「知识图谱暂时不可用」从一次故障变成一次可观测的降级。

**Blocked by:** 07（orchestration 正常路径）

**Status:** done
Completed: 0bb0b7c

- [x] 向量检索或图谱不可用时问答仍完成，HTTP 状态仍为 200
- [x] `done.degraded` 列出不可用支路（`retrieval` / `graph`）
- [x] 降级不产生错误码，符合「降级与失败区分」的约定
- [x] 大模型生成不可用无法降级，返回 503 / 504
- [x] 端到端场景「图谱不可用 + 头疼发烧」：HTTP 200，`done.degraded` 含 `graph`，回答仍生成
