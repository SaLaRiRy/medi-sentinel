# 22: 数据统计

**What to build:** 三端各自的概览：患者看到个人概览，医生看到工作台概览，管理员看到运营概览与趋势、分布类图表数据。

**Blocked by:** 12（认证与个人中心）

**Status:** done
Completed: 97efeab0c758d6b45f4e46fc9ca9c4b764a0e176

- [x] 管理员概览与医生概览可用，字段按角色不同
- [x] 患者个人概览可用
- [x] 问诊趋势与用户增长支持按天数查询；预约科室分布与知识库类型分布可用
- [x] 未知状态值回退到既定默认展示
- [x] 天数等查询参数越界返回 422

## Comments

落地内容（`SPEC.md` 5.4「内容与统计」六个端点，全部只读、不新增迁移）：

- 后端：新增 `repositories/stat.py`（异步聚合）、`services/stat_service.py`（规则，
  与 `FUNCTIONAL_SPEC.md` 2.9 的函数同名）、`api/v1/stat.py`（路由）。管理员
  `GET /stat/overview` 返回患者/医生/AI 会话/预约/知识文件/文章六项总数；同一端点
  对医生返回 `pending_consults` / `today_appointments` / `replied_consults` /
  `total_patients` 四项，**字段按角色不同**（另一角色字段由
  `response_model_exclude_none=True` 略去）。`GET /stat/user-overview` 只给患者。
  `GET /stat/consult-trend`、`GET /stat/user-growth` 按 `days`（默认 7）返回
  `{date, count}[]`；`GET /stat/appointments-by-department` 返回每个科室的预约数
  （无预约计 0）；`GET /stat/knowledge-types` 按文件类型统计。
- 前端：经唯一出口 `api/client.js` 暴露六个调用；新增 `AdminDashboardView.vue`
  （六项总数 + 两条趋势 + 两个分布，可切换统计天数）与 `DoctorDashboardView.vue`
  （四项工作台指标），患者首页 `PortalHomeView.vue` 并入个人概览；三处概览共用
  `components/StatGrid.vue`。加载失败呈现空态而非错误页。`contracts/openapi.json`
  由 `scripts/export_contract.py` 重新生成（未手改），`sse-events.json` 未动。

语义与取舍（逐条结论）：

- **「未知状态值回退到既定默认展示」**：统计端点本身没有数值状态维度，唯一开放的
  字符串维度是知识库类型（`t_knowledge_file.file_type` 由扩展名映射，未识别落为
  `unknown`）。新增 `client/src/stat/labels.js` 的 `knowledgeTypeLabel`，未知类型
  回退到既定默认「未知类型」，与既有状态映射（向量化未知回退「未知状态」）一致
  （AC-F-11）。
- **`days` 越界**：`FUNCTIONAL_SPEC.md` 5.9 记的是「无上下界约束」，但 `SPEC.md`
  5.4 为两个趋势端点声明 422，本票据此施加 `1..365`，越界返回 422（与既有分页
  参数「契约声明 422 即须真实可触发」的口径一致）。
- **自然日口径**：按 **UTC** 计算。模型时间戳由 `datetime.now(UTC)` 生成，SQLite
  以朴素 UTC 墙钟存取（`repositories/trace.py`），因此按存储值的日期分桶即自洽；
  SPEC 未规定时区。
- **患者概览落点**：`FUNCTIONAL_SPEC.md` 1.4 把统计映射到 `portal/Home.vue`，故
  并入既有患者首页（公告保留、行为不变），与本票「患者个人概览可用」一致。
- **声明补齐**：六个新端点自带 `responses=error_responses(...)`，并加入
  `tests/test_declared_error_branches.py`（沿用 020/021 的全覆盖模式）。

挂账：无。本票边界明确不含 23–24（回归基线与端到端验收）。
