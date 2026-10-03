# 06: graph-inference 图谱推理 Skill

**What to build:** 由标准症状集合反查可能疾病并按覆盖率排序的能力，独立于大模型。患者给出症状后，医生与患者都能看到「依据了哪些症状、为什么排在前面」的候选疾病列表。

**Blocked by:** 02（Skill 协议与 trace 基座）、04（症状归一化 Skill）

**Status:** ready-for-agent

- [ ] 标准症状集合 → 候选疾病有序列表，`coverage = 命中数 ÷ 输入症状数`，保留 2 位小数
- [ ] `department` 缺失时返回 `null`，不是字符串 `"-"`
- [ ] 无最低命中阈值；截断规则显式化并写入 trace，不存在静默截断
- [ ] 对外字段名为 `coverage`，不存在 `probability`
- [ ] 图谱不可用时返回 `degraded`，不抛错
- [ ] 与归一化共用同一份词表：同一输入在两条链路输出同一标准症状集合
- [ ] `SKILL.md` 四节齐备，用例已转为可执行测试且全部通过
