# 08: 安全门短路路径

**What to build:** 红旗命中时的全链路短路：不调用大模型，也不执行归一化、检索与图谱，直接产出安全提示并结束流。这条路径是「急症输入必定被流程拦截」的落点，不能再依赖模型的服从程度。

**Blocked by:** 07（orchestration 正常路径）

**Status:** ready-for-agent

- [ ] 红旗输入的 SSE 流出现 `safety` 帧且 `decision == intercept`
- [ ] 同一输入大模型端口调用次数为 0
- [ ] 同一输入图谱与检索端口调用次数均为 0
- [ ] 同一输入归一化 Skill 调用次数为 0
- [ ] `content` 帧次数为 0；`route.skills_run == ["safety-gate"]`；`done` 的 `references` 与 `graph` 均为空
- [ ] trace 中只有 `safety-gate` 一条 Skill span，无大模型 span
- [ ] 非红旗输入不出现 `safety` 帧，且流中出现 `content` 帧
