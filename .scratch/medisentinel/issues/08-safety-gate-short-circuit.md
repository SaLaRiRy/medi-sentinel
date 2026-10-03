# 08: 安全门短路路径

**What to build:** 红旗命中时的全链路短路：不调用大模型，也不执行归一化、检索与图谱，直接产出安全提示并结束流。这条路径是「急症输入必定被流程拦截」的落点，不能再依赖模型的服从程度。

**Blocked by:** 07（orchestration 正常路径）

**Status:** done
Completed: 0e33191

- [x] 红旗输入的 SSE 流出现 `safety` 帧且 `decision == intercept`
- [x] 同一输入大模型端口调用次数为 0
- [x] 同一输入图谱与检索端口调用次数均为 0
- [x] 同一输入归一化 Skill 调用次数为 0
- [x] `content` 帧次数为 0；`route.skills_run == ["safety-gate"]`；`done` 的 `references` 与 `graph` 均为空
- [x] trace 中只有 `safety-gate` 一条 Skill span，无大模型 span
- [x] 非红旗输入不出现 `safety` 帧，且流中出现 `content` 帧

## 交付物

- `server/skills/orchestration/skill.py`：拦截分支（`_short_circuit`）：先记路由决策，再发
  `route → safety → done`，然后结束流；拦截路径不写 `orchestration` span。
- `server/skills/orchestration/frames.py`：新增 `safety_payload`（安全门输出 → `safety` 帧
  的投影，裁掉 `rule_version` 与 `decision`）；`done_payload` 改为显式接收 `coverage_note`，
  以便拦截路径写 `null`。
- `server/skills/safety_gate/{rules,skill}.py`：输出用语对齐冻结契约（见下）。
- `server/skills/safety_gate/SKILL.md`、`server/skills/orchestration/SKILL.md`：同步改写。
- 测试：`tests/test_safety_gate_short_circuit.py`（8 条）+ `tests/test_safety_gate_skill.py`
  的新增/改写用例。

## 跨票挂账结算：TICKET-007 挂账第 1 条（硬约束）

**问题**：安全门 Skill 输出用 `critical` / `matched_text` / 每项 `level`，而冻结的
`contracts/sse-events.json` 的 `safety` 帧要求 `emergency` / `matched_surface` / 每项
`severity`。对齐方向必须拍板。

**结论：改实现侧——安全门 Skill 输出改用冻结契约的用语；`contracts/` 不动。**

- **为什么不是反向**：契约是 C-1 seam 的唯一依据（`SPEC.md` 3.9 / 5.6）；`SPEC.md` 5.5
  本身也已经按 `emergency` / `matched_surface` 冻结。两侧不可能同时为真，故优先改实现侧。
- **契约本身没有错**：`emergency` 与 `critical` 同义（都是「立即急诊」），
  `matched_surface` 是「命中的表层字符串」的通行叫法。反向改契约会波及已冻结的前端消费方
  （F-1/F-2），收益为零。因此**未更新 `contracts/`**。
- **落地**：`RedFlagLevel = Literal["urgent", "emergency"]`；`RedFlagMatch` 字段名改为
  `id` / `matched_surface` / `severity` / `label`。`SafetyGateOutput` 因而可被
  `safety_payload` 原样投影为 `safety` 帧，不再需要第二张映射表。
- **契约测试覆盖该帧**：
  `test_safety_frame_matches_the_frozen_sse_contract` 用 `Draft202012Validator` 校验
  `safety` 帧，并断言 `red_flags[]` 的字段名与契约逐字一致；
  `test_output_speaks_the_frozen_sse_contract_vocabulary` 在 B-2 seam 上锁住 Skill 输出的字段名。

## 仍在本票之外、留给后续票的接口

| 项 | 归属 |
|---|---|
| 拦截路径的助手消息落库语义：`api/v1/chat.py` 在收到 `done` 时落一条助手消息，拦截路径 `answer` 为 `""`（安全提示只走 `safety` 帧）。历史接口要展示安全提示时需一并定夺 | TICKET-014（会话历史/前端） |
