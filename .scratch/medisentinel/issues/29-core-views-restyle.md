# 29: 核心视图 element-plus 重做

**What to build:** 把患者/医生高频视图改成 element-plus 组件，观感明显改善，同时保留 data-* 锚点、F-1 唯一出口与路由/守卫/pinia 语义。

**Blocked by:** 28

**Status:** ready-for-agent

背景：028 完成基础设施（vue-router/pinia/element-plus 外壳），health 探针竞态已修（fcec3d8）。视图内部仍是手写 HTML，观感朴素。本票把患者/医生高频视图改成 element-plus 组件。

**范围（患者 + 医生核心页）：**

- ChatView（AI 问诊对话）—— 消息气泡、输入框、发送按钮、safety 帧展示、degraded 标记
- SymptomView（症状推理）—— 候选疾病、coverage 展示
- AppointmentView + DoctorAppointmentsView（预约）
- RecordsView + DoctorPatientsView（健康档案）
- ConsultView + DoctorConsultsView（人工问诊工单）
- ProfileView（个人中心）
- PortalHomeView（患者首页）
- 登录/注册页（PublicShell 里的表单）

每页要求：

- 表单类：el-form / el-input / el-select / el-date-picker
- 列表类：el-table / el-pagination
- 反馈类：el-message / el-notification / el-loading
- 状态标签：el-tag / el-badge
- 对话气泡：el-card + 自定义样式（element-plus 无现成气泡）
- 保留所有 data-* 属性和可测试的 DOM 锚点，否则会打断既有测试
- 保留 F-1 唯一出口（api/client.js 不变）
- 保留路由/守卫/pinia 语义不变

**验收清单：**

- [ ] 上述视图全部改用 element-plus 组件
- [ ] 既有前端测试绿（若因 DOM 变化需同步调整测试，明确报告调整数量，断言强度不降）
- [ ] npm run build 成功
- [ ] 页面观感明显改善
- [ ] 无 F-1 架构测试破裂
- [ ] ticket Comments 记录：改了哪些视图、测试调整统计、element-plus 兼容问题

**边界：**

- 不改后端
- 不改管理端视图（030 再做）
- 不改 router/store/guard 语义
- 不改 001–028 的行为

## Comments
