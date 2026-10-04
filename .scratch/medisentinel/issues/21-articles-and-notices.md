# 21: 健康科普与公告

**What to build:** 面向公众的健康科普文章与系统公告：公开的列表与详情，加上管理员的增删改查与分页管理。

**Blocked by:** 12（认证与个人中心）

**Status:** done
Completed: 3749de1da0fffa058cb905e590a1ab7228742cdf

- [x] 公开的文章列表与详情、公告列表与详情可用；文章可按分类过滤
- [x] 管理员对文章与公告的增删改查与分页可用
- [x] 更新或删除不存在的记录时保持现状语义（不新增存在性校验）
- [x] 列表加载失败呈现空状态，而非错误页或空白
- [x] 分页列表删除最后一条时页码回退

## Comments

落地内容（`SPEC.md` 5.4「内容与统计」）：

- 后端：新增迁移 `0011` 与 `t_article` / `t_notice` 两张独立表（无任何关联），并在
  `api/v1/{articles,notices}.py` 落地 12 个端点。公开侧 `GET /articles`（分页 +
  `category?` 过滤，`ArticleListView` 不含正文）与 `GET /articles/{id}`（详情，命中
  已发布时 `view_count + 1` 并提交，`FUNCTIONAL_SPEC` 5.17）无需认证；`GET /notices`
  为**不分页**的已发布公告数组，`GET /notices/{id}` 仅已发布。管理侧
  `/{articles,notices}/admin` 分页看全部状态，`POST`/`PUT`/`DELETE` 限 `admin`。
- 前端：经唯一出口 `api/client.js` 暴露 12 个调用；新增患者门户首页公告与
  `/portal/articles` 科普阅读（分类过滤、详情、可返回），以及
  `/admin/{articles,notices}` 管理视图。文章/公告状态映射 `1 → 已发布（success）/
  其余 → 已下架（info）`（`client/src/content/status.js`）。列表加载失败置空列表并
  呈现空态；分页列表删除当前页最后一条时页码回退。`contracts/openapi.json` 由
  `scripts/export_contract.py` 重新生成（未手改）；`sse-events.json` 未动。

语义与取舍（逐条结论）：

- **「记录不存在」的语义**：验收清单第 3 条写「保持现状语义（不新增存在性校验）」，
  而 `FUNCTIONAL_SPEC.md` 1540 旧行为是「更新、删除恒返回成功」。本票以 `SPEC.md`
  5.4 为准（PUT/DELETE 声明 404）与项目统一语义（与 015/017/018/019/020 一致）：
  **更新/删除不存在的记录返回 404**，不新增其他存在性校验。
- **公开详情范围**：公开列表与详情都只暴露已发布（`status == 1`）记录，未发布或
  不存在一律 404 —— 旧的公告详情 `data: null` 收进真实状态码（SPEC 5.1/5.2）。
- **公开文章列表分页**：`FUNCTIONAL_SPEC.md` 5.9 对「文章公开列表」标注页码页长无
  约束，但 `SPEC.md` 5.4 为该端点声明 422，故本票按 `PageQuery` 施加 `page ≥ 1`、
  `page_size 1..100`，越界返回 422。
- **角色**：SPEC 5.4 把内容读取标为「公开」，患者与医生均可读；因 AC-F-10 固定医生
  菜单为 4 项，前端只在患者门户提供阅读入口，医生经公开 API 读取。
- **声明补齐**：新端点自带 `responses=error_responses(...)`，并加入
  `tests/test_declared_error_branches.py`（沿用 020 的全覆盖模式）。
