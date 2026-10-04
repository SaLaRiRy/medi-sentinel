# 30: 管理端视图 element-plus 重做

**What to build:** 把管理端（及共享管理页）视图改成 element-plus 组件，观感与 029 的患者/医生端一致，同时保留所有 data-* 锚点、F-1 唯一出口与路由/守卫/pinia 语义。

**Blocked by:** 29

**Status:** done
Completed: fdba2d7d5681ae49def67c249aa193782d18984c

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

- [x] 上述管理端视图全部改用 element-plus 组件
- [x] 既有前端测试绿（若因 DOM 变化需同步调整，明确报告调整数量，断言强度不降）
- [x] npm run build 成功
- [x] 页面观感与 029 的患者/医生端一致
- [x] 无 F-1 架构测试破裂
- [x] ticket Comments 记录：改了哪些视图、测试调整统计、EP 兼容问题（若有新的）

**边界：**

- 不改后端
- 不改 029 已重做的患者/医生视图
- 不改 router/store/guard 语义
- 不改 001–029 的行为

**开工前：**

1. ls .scratch/medisentinel/issues/ 确认 30 是否存在
2. git status 确认在 main、工作区干净
3. 读 client/src/views/ 现状，报告要改的管理端视图清单与行数

## Comments

### 开工前报告（行数按改动前统计）

在 `main`、工作区干净（HEAD `737e6b4`）。ticket 文件原本不存在，已按用户提供的
TICKET 内容创建。管理端/共享管理页共 **11 个视图** 需重做：

| 视图 | 行数 |
|---|---|
| `AdminAppointmentsView.vue` | 175 |
| `AdminArticlesView.vue` | 179 |
| `AdminConsultsView.vue` | 122 |
| `AdminDashboardView.vue` | 155 |
| `AdminDepartmentsView.vue` | 181 |
| `AdminDoctorsView.vue` | 283 |
| `AdminNoticesView.vue` | 158 |
| `AdminUsersView.vue` | 256 |
| `DoctorDashboardView.vue` | 59 |
| `GraphView.vue` | 149 |
| `KnowledgeView.vue` | 192 |

`SymptomView.vue` 属患者侧且 029 已完成重做，按本票「不改 029 已重做的患者/医生
视图」边界不动。

### 改了哪些视图（11 个）与所用 element-plus 组件

| 视图 | element-plus 组件 |
|---|---|
| `AdminUsersView.vue` | el-card ×2 + el-form/el-input/el-select + el-table/el-tag + el-button + el-pagination |
| `AdminDoctorsView.vue` | el-card ×2 + el-form/el-input/el-select + el-table/el-tag + el-button + el-pagination |
| `AdminDepartmentsView.vue` | el-card ×2 + el-form/el-input + el-table/el-tag + el-button + el-pagination |
| `AdminArticlesView.vue` | el-card ×2 + el-form/el-input/el-select(textarea) + el-table/el-tag + el-button + el-pagination |
| `AdminNoticesView.vue` | el-card ×2 + el-form/el-input/el-select(textarea) + el-table/el-tag + el-button + el-pagination |
| `AdminConsultsView.vue` | el-card + el-select(过滤) + el-table/el-tag + el-button + el-pagination |
| `AdminAppointmentsView.vue` | el-card + el-form/el-input/el-select/el-date-picker(过滤) + el-table/el-tag + el-button + el-pagination |
| `AdminDashboardView.vue` | el-card(概览 + 4 张面板) + el-select(统计天数) + el-tag(数值) + v-loading |
| `DoctorDashboardView.vue` | el-card + v-loading（StatGrid 复用） |
| `KnowledgeView.vue` | el-card + el-form/el-input/el-select + el-upload + el-table/el-tag + el-button + el-pagination |
| `GraphView.vue` | el-card + el-form/el-input/el-select + el-button + el-tag(节点) |

反馈类统一 `ElMessage`（增删改成功）+ `v-loading`（列表/概览加载）；状态标签统一
`el-tag`。`api/client.js`（F-1）未改，router/store/guard 未改，后端未改。

### 测试调整统计（断言强度不降）

- 基线 **54 文件 / 307 测试** → 完成 **55 文件 / 320 测试** 全绿（+1 文件 / +13）。
- 新增 `tests/element-plus-admin-views.test.js`（11 测试）：逐视图断言本票要求的
  element-plus 组件确实存在（结构一致性，TDD 红→绿驱动）。
- 新增 2 条回归测试（`admin-doctors-view` / `admin-articles-view`）：覆盖
  el-select `clearable` 清空后的载荷，防止 `NaN` / 崩溃。
- 调整既有测试 **10 文件**（`admin-users` / `admin-doctors` / `admin-departments`
  / `admin-articles` / `admin-notices` / `admin-consults` / `admin-appointments`
  / `admin-dashboard` / `graph` / `knowledge`），均为「DOM 变化导致」的等价改法：
  1. 行分组：`[data-*-row]` → `.el-table__row`（ElTable 不给 `<tr>` 写属性）。
  2. 组件交互：`[data-department|category|status|file-type|status-filter|
     filter-status|days|depth]` 由 `find().setValue` 改为 `findComponent().setValue`。
  3. 日期：`[data-filter-visit-date]` → `findComponent(ElDatePicker).setValue`。
  4. 翻页：`[data-prev|next|next-page]` → `.btn-prev` / `.btn-next`（el-pagination
     拥有页码按钮，无法把 data-* 落到内部 button）。
  5. 行内操作：`[data-set-status|delete|revectorize]` 收敛到 `.el-table__row`
     （ElTable 会为测宽渲染一份隐藏副本）。
  6. 上传：`[data-upload]` → `[data-upload] input[type="file"]`（el-upload 内部
     input 承载 change 事件，锚点仍在组件根）。
  7. `[data-department-option]`：由 `attributes('value')` 改为 `props('value')`
     （el-option 不把 value 渲染成属性），断言值不变。
- `doctor-dashboard-view.test.js` 零改动。

### element-plus 兼容问题（本票新增/沿用）

沿用 029 已记录的处理方式：ElTable 无行 attrs 通道 → `.el-table__row`；
ElTableColumn 隐藏测宽副本 → 行内操作收敛；el-select attrs 落根 div、el-option
无 value 属性；el-date-picker 不转发 attrs → 包外壳；el-card `overflow:hidden`
裁下拉 → 表单卡片显式 `overflow: visible`；按需引入保持生效（产物中
`el-carousel/el-calendar/el-tree/…` 样式计数为 0，未引入全局 index.css）。

**本票新发现：**
1. **el-pagination 不提供按钮级 attrs 通道**：页码/上一页/下一页按钮由组件内部
   渲染，`data-prev`/`data-next`/`data-page` 无法落到 button 上；改用组件稳定类名
   `.btn-prev`/`.btn-next` 驱动测试，并保留 `data-pagination` 根锚点。断言等价。
2. **el-select `clearable` 清空值为 `undefined`**（EP `valueOnClear` 默认
   `undefined`，非 `''`）：直接沿用 029 的「空串」假设会让 `payload()` 出现
   `department_id: NaN` 或 `category.trim()` 抛错。处理：清空值显式设为
   `value-on-clear=""` 并加空值防御；补 2 条回归测试。
3. **el-select 不再触发原生 `change`**（程序化 model 更新不冒泡 `change`）：
   AdminConsults 的状态过滤、AdminDashboard 的统计天数、GraphView 的邻域深度改为
   `watch(model, …)` 触发重载，行为与原生 `@change` 等价，并在代码注释说明。
4. **el-upload 需内部 input 驱动**：`data-upload` 落在组件根 div，文件选择事件在
   内部 `<input type="file">`，测试锚点下钻到该 input；上传/回显/轮询语义不变。

### 边界与偏差

- `api/client.js` 未改（F-1 单出口架构测试通过）；router/store/guard 未改；后端未改；
  029 已重做的患者/医生视图未改（`SymptomView` 除外亦未动）。
- 7 个列表视图的卡片/表格/分页骨架存在重复模板，遵从 029 既有取舍不再抽公共组件
  （各表列与载荷不同，抽取属 speculative generality）。已记入评审结论。

### /code-review（两轴独立评审，未合并）

subagent 通道已知投递失败，按指示直接走 fallback：对同一 diff
`git diff 737e6b4...fdba2d7` 独立跑两遍评审，分别报告。

**Standards 轴**

- 标准来源：`AGENTS.md`、`docs/agents/{issue-tracker,triage-labels,domain}.md`、
  `docs/tech-debt.md`、ADR 0001/0002，外加 Fowler 味道基线。仓库无
  `CODING_STANDARDS.md` / `CONTRIBUTING.md`。
- **已修-1｜状态着色映射重复**：`KnowledgeView` 内联 `{0:'info',…}`，而仓库惯例是
  把 `xxxStatusColor` 放在各域 `status.js`（`accountStatusColor` /
  `contentStatusColor` / `appointmentStatusColor` / `consultStatusColor`）。
  → 抽到 `knowledge/status.js` 的 `vectorStatusColor`，视图改用之。
- **已修-2｜clearable 语义破坏**：见上「本票新发现 2」。
- **判断项（接受）｜Duplicated Code**：7 个列表视图的卡片/表格/分页骨架重复；029
  对 12 个视图采用同一取舍，列与载荷各异，现抽公共组件属 Speculative Generality。
- **判断项（接受）｜watch 取代 @change**：为 el-select 引入 `watch(model)` 重载，
  已加注释说明，行为等价。
- 无硬性违规：F-1 未触碰（架构测试通过）；`data-*`/中文注释/票号引用符合仓库风格；
  视图层无传输调用。合计：**2 项已修 / 2 项判断项（接受）/ 0 项遗留硬违规**。

**Spec 轴**

- 规格来源：本 ticket（`30-admin-views-restyle.md`）+ SPEC.md §3/§4/§6。
- **缺失/部分**：本票写作「GraphView + SymptomView 管理端部分」，但 `SymptomView`
  是患者侧且 029 已完成；管理端菜单无独立症状页。按本票「不改 029 已重做视图」的
  边界，**有意不纳入**（非遗漏）。GraphView 已重做。
- **已报告的等价替换**：el-pagination 的 `data-prev/next/page` 锚点被移除，改用
  `.btn-prev/.btn-next` + `data-pagination`；断言强度不变（见「本票新发现 1」）。
- **越界**：无。后端 / router / store / guard / `api/client.js` 均未改；029
  患者/医生视图未改。
- **看似实现但可能有误**：修复 clearable 后无遗留；F-1、build、按需引入、320 测试
  全绿均已复核。合计：**0 项开放缺口（1 项有意排除 + 1 项已报告替换）/ 0 项越界**。
