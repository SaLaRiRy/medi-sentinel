# 11: 可观测性对外接口与 Skill 清单

**What to build:** 把 trace 与 Skill 清单开放出来：管理员按 `trace_id` 看到一次问诊的全部 span 与路由决策，按条件检索历史 trace，任何已认证用户能查到五个 Skill 的名称、类别、Schema 版本与词表版本。

**Blocked by:** 07（orchestration 正常路径）

**Status:** ready-for-agent

- [ ] `GET /traces/{trace_id}` 返回该次问诊的全部 span 与路由决策
- [ ] `GET /traces` 支持按 trace_id、Skill 名、时间范围、是否降级分页检索
- [ ] `GET /skills` 返回五个 Skill 的名称、类别、Schema 版本与词表版本
- [ ] 对同一 trace_id 重复检索结果稳定
- [ ] trace 内容足以在不访问外部依赖的前提下重放该次问诊并得到相同结果
- [ ] 非管理员访问追踪检索类端点返回 403
