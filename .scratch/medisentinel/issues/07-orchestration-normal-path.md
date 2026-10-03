# 07: orchestration 编排 Skill：正常路径 SSE 编排

**What to build:** 一次问诊的完整编排：生成 trace、先过安全门、归一化、并行跑向量检索与图谱推理、组装上下文、调用大模型流式生成，并把全过程以 SSE 事件流推给前端。这是唯一调用大模型的 Skill。

**Blocked by:** 03（safety-gate）、04（symptom-normalization）、05（vector-retrieval）、06（graph-inference）

**Status:** ready-for-agent

- [ ] `POST /api/v1/chat/send` 端到端流式问答可用；会话标题按前 20 字符 + 省略号生成，消息计数 +2，历史取最近 6 条
- [ ] `session` 与 `trace` 必为前两帧且顺序固定；正常路径不出现 `safety` 帧；`done` 恰好一次；`done` 与 `error` 互斥且流以二者之一结束
- [ ] 正常路径 `skills_run` 恰好包含五个 Skill；同一输入同一配置下路由完全一致
- [ ] 归一化输出为空时跳过图谱推理，并在 `skills_skipped` 中给出理由
- [ ] 向量检索与图谱推理并行执行、互不筛选
- [ ] 提示词组装规则与现状一致：安全约束 4 条、上下文注入位置、历史截断条数
- [ ] 端到端场景「我头疼发烧三天了」：归一化产出含 `头痛`、`发热`；图谱返回候选疾病；`content` 帧非空；`done` 含引用与候选；trace 含 5 条 Skill span + 1 条大模型 span
