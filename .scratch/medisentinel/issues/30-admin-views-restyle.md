# 30: 管理端视图 element-plus 重做

**What to build:** 把管理端（及共享管理页）视图改成 element-plus 组件，观感与 029 的患者/医生端一致，同时保留所有 data-* 锚点、F-1 唯一出口与路由/守卫/pinia 语义。

**Blocked by:** 29

**Status:** ready-for-agent

背景：029 完成了患者/医生核心页的 element-plus 重做（12 个组件）。管理端列表页仍为手写 HTML。本票收尾，把管理端视图统一到 element-plus。

**范围（管理端 + 共享管理页）：**

- AdminUsersView（用户管理）
- AdminDoctorsView（医生管理）
- AdminDepartmentsView（科室管理）
- AdminArticlesView + AdminNoticesView（内容管理）
- AdminConsultsView + AdminAppointmentsView（工单/预约管理）
- AdminDashboardView + DoctorDashboardView（仪表盘，含统计）
- KnowledgeView（知识库管理，含 3s 轮询逻辑）
- GraphView + SymptomView 管理端部分（图谱可视化、症状推理）

每页要求（沿用 029 模式）：

- 表单类：el-form / el-input / el-select / el-date-picker
- 列表类：el-table + el-pagination（有分页的端点）
- 反馈类：ElMessage / v-loading
- 状态标签：el-tag
- 保留所有 data-* 属性和可测试的 DOM 锚点；若 EP 限制导致必须改选择器（如 el-table 行），报告并保持断言等价
- 保留 F-1 唯一出口（api/client.js 不变）
- 保留路由/守卫/pinia 语义不变

**【029 已发现的 EP 兼容问题（沿用处理方式）】**

- ElTable 无行 attrs 通道 → 用 .el-table__row 选择器
- ElTableColumn 会渲染隐藏测宽副本（row:{}、$index:-1）→ 断言时过滤
- el-select attrs 落根 div、el-option 无 value 属性
- el-date-picker 不转发 attrs → 包外壳
- el-card overflow:hidden 与下拉冲突 → 表单卡片 overflow:visible
- 按需引入保持生效（产物不应含未用组件的样式）

**验收清单：**

- [ ] 上述管理端视图全部改用 element-plus 组件
- [ ] 既有前端测试绿（若因 DOM 变化需同步调整，明确报告调整数量，断言强度不降）
- [ ] npm run build 成功
- [ ] 页面观感与 029 的患者/医生端一致
- [ ] 无 F-1 架构测试破裂
- [ ] ticket Comments 记录：改了哪些视图、测试调整统计、EP 兼容问题（若有新的）

**边界：**

- 不改后端
- 不改 029 已重做的患者/医生视图
- 不改 router/store/guard 语义
- 不改 001–029 的行为

**开工前：**

1. ls .scratch/medisentinel/issues/ 确认 30 是否存在
2. git status 确认在 main、工作区干净
3. 读 client/src/views/ 现状，报告要改的管理端视图清单与行数
