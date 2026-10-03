# 03: safety-gate 安全门 Skill

**What to build:** 独立的 Process Rules Skill，在编排第一顺位、任何大模型调用之前对输入做确定性的红旗检测。患者描述急症（如「胸口剧痛，出冷汗，喘不上气」）时返回拦截决策，附命中项、严重级与建议动作；普通描述返回放行。

**Blocked by:** 02（Skill 协议与 trace 基座）

**Status:** ready-for-agent

- [ ] `SKILL.md` 四节齐备（输入输出 Schema、触发条件、边界情况、测试用例），且内容与运行时行为一致
- [ ] 同一输入连续运行 100 次，`decision` 与 `red_flags` 完全一致
- [ ] 否定式表述（「没有胸痛」「不发烧」）不触发拦截
- [ ] 多条红旗同时命中时返回全部命中项，`level` 取最高严重级
- [ ] `decision == intercept` 时 `message` 与 `suggested_action` 均非空
- [ ] trace 记录命中的红旗标识、匹配到的原文片段与依据的规则版本号
- [ ] 以「大模型端口抛异常的假实现」注入运行时全部测试仍通过
- [ ] `SKILL.md` 中的测试用例已转为可执行测试且全部通过
