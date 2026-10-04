# 29: 核心视图 element-plus 重做

**What to build:** 把患者/医生高频视图改成 element-plus 组件，观感明显改善，同时保留 data-* 锚点、F-1 唯一出口与路由/守卫/pinia 语义。

**Blocked by:** 28

**Status:** done
Completed: ab88433f1857258752a2f7749bf15ad8e5c970e1

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

- [x] 上述视图全部改用 element-plus 组件
- [x] 既有前端测试绿（若因 DOM 变化需同步调整测试，明确报告调整数量，断言强度不降）
- [x] npm run build 成功
- [x] 页面观感明显改善
- [x] 无 F-1 架构测试破裂
- [x] ticket Comments 记录：改了哪些视图、测试调整统计、element-plus 兼容问题

**边界：**

- 不改后端
- 不改管理端视图（030 再做）
- 不改 router/store/guard 语义
- 不改 001–028 的行为

## Comments

### 改了哪些视图（12 个组件）

| 组件 | element-plus 组件 |
|---|---|
| `ChatView.vue` | el-card 气泡 + el-input(textarea) + el-button + el-tag（degraded）+ el-progress（coverage） |
| `SymptomView.vue` | el-form + el-input + el-button + el-tag（症状）+ el-card/el-tag/el-progress（候选） |
| `AppointmentView.vue` | el-form + el-select + el-date-picker + el-input + el-table + el-tag |
| `DoctorAppointmentsView.vue` | el-table + el-tag（状态）+ el-button（操作） |
| `RecordsView.vue` | el-table |
| `DoctorPatientsView.vue` | el-form + el-select + el-date-picker + el-input + el-table + el-button |
| `ConsultView.vue` | el-form + el-input + el-table + el-tag |
| `DoctorConsultsView.vue` | el-table + el-input + el-button |
| `PortalHomeView.vue` | el-card + el-table（公告） |
| `LoginView.vue` / `RegisterView.vue` | el-card + el-form + el-select + el-input + el-button |
| `components/ProfilePanel.vue`（`ProfileView` 面板） | el-card + el-form + el-input + el-button + el-divider |
| `components/SafetyCard.vue`（ChatView safety 帧） | el-card + el-tag + el-alert |

反馈类用 `ElMessage`（提交成功）+ `v-loading`（异步加载）；状态标签用 `el-tag`。
`el-notification` / `el-badge` / `el-pagination` 未使用：本票范围内的列表端点
（myAppointments / doctorRecords / pendingConsults / notices 等）均**不分页**，
加 el-pagination 属臆造；不加即符合「列表类用 el-table」且避免 speculative generality。

### 测试调整统计（断言强度不降，无删断言）

- 基线 **53 文件 / 295 测试** → 完成 **54 文件 / 307 测试** 全绿。
- 新增 `tests/element-plus-views.test.js`（1 文件 / 12 测试）：结构一致性断言，
  逐视图断言本票要求的 element-plus 组件确实存在（红→绿参考 TDD 驱动）。
- 改动既有测试 **8 文件**，均为「DOM 变化导致的不得不改」，逐条等价或更强：
  1. 行分组：`[data-*-row]` → `.el-table__row`（ElTable 不支持给 `<tr>` 写属性）。
  2. 表单交互：`[data-role|doctor-id|department-id|time-slot|patient-select|record-type]`
     由 `find().setValue` 改为 `findComponent().setValue`（el-select 是组件）。
  3. 日期：`[data-visit-date]` → `findComponent(ElDatePicker).setValue`
     （el-date-picker 不转发 attrs）。
  4. 行内操作：`[data-set-status|edit|delete|reply-*|open]` 作用域收紧到 `.el-table__row`
     （ElTable 会为测宽额外渲染一份隐藏 cell）。
  5. `[data-patient-option]`：由 `attributes('value')` 改为 `props('value')`
     （el-option 不把 value 渲染成属性），断言值不变。
  6. 预约「提交失败不清空表单」：由 `element.value` 改为 `props('modelValue')`，语义等价。
- `chat-view` / `symptom-view` / `records-view`（除行分组外）等其余行为测试零改动。

### element-plus 兼容问题（实测）

1. **ElTable 行属性**：`ElTable` 渲染 `<tr>` 时只带 style/class/handler，无 attrs 通道，
   规范里「保留 data-*」的 `data-*-row` 行锚点无法落在 `<tr>` 上；行分组改用
   `.el-table__row`（库的稳定行元素）。cell 级 `data-cell-*` 锚点全部保留。
2. **ElTableColumn 隐藏测宽副本**：`ElTableColumn` 会调用一次 default slot
   `{ row: {}, column: {}, $index: -1 }` 渲染到 `.hidden-columns` 测宽，导致每个
   cell 内容在 DOM 里出现两份。行内交互测试必须收窄到 `.el-table__row`，否则会点到
   隐藏副本（`row.id` 为 undefined）。
3. **el-input 转发 attrs**：attrs 落到内层原生 `<input>/<textarea>`，
   `data-*` 锚点与 `setValue` 交互保持可用（chat/consult/auth/records 省去大量改动）。
4. **el-select**：attrs 落在组件根 `<div>`，需组件级驱动；el-option 不渲染 `value` 属性。
5. **el-date-picker**：不转发 attrs，故日期锚点包一层 `<span data-visit-date>` 保留。
6. **下拉裁剪**：为使选项锚点留在组件树内对 el-select 用 `:teleported="false"`；
   el-card 默认 `overflow:hidden`、`.el-card__body` 默认 `overflow:auto` 会裁掉下拉，
   已在 Appointment / DoctorPatients 表单卡片上显式 `overflow: visible`。
7. **按需引入未破**：产物中 `el-carousel/el-calendar/el-upload/el-tree/el-transfer`
   样式计数为 0，未引入完整 `element-plus/dist/index.css`；构建成功
   （css 157.9 kB / js 655.4 kB）。

### 边界与偏差

- `api/client.js` 未改（F-1 单出口架构测试通过）；router/store/guard 语义未改；后端未改。
- `ProfilePanel` 为三角色共用的个人中心面板，改它会让管理端「个人中心」页一并更新外观
  （管理端**列表页**未动，留 030）——本票把 `ProfileView` 列入范围，故属必要落点。
- 提交/更新/删除成功新增 `ElMessage` 轻提示（反馈类要求）；不改变任何接口调用与数据语义。
- `data-remove-symptom` 锚点由 el-tag 的内置关闭按钮取代（el-tag 关闭图标无法挂 attrs），
  该锚点无测试引用；`data-symptom-tag` 保留。
