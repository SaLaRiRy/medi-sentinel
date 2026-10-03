# 01: 工程骨架与契约 seam

**What to build:** 一个可演示的 walking skeleton：monorepo 下 `client/` 与 `server/` 能同时起得来，前端页面经唯一出口模块调用后端的一个健康端点并显示结果；后端以异步会话与仓储层访问数据库，Schema 由 Alembic 迁移管理；机器可读的接口契约（REST 描述 + SSE 事件 Schema）成为两侧唯一事实来源，前后端各自的契约测试都能跑通。

**Blocked by:** None（可立即开始）

**Status:** done
Completed: 287a5ea

- [x] 前端启动后能从页面看到后端健康状态，请求经由 F-1 唯一出口模块发出，视图层没有直接的传输调用
- [x] 错误码承载在真实 HTTP 状态码上，响应体 `code` 与状态码一致；不存在「HTTP 200 + 非 200 的 code」
- [x] 统一响应外壳与分页载荷形状（`items` / `total` / `page` / `page_size`）在骨架端点即成立
- [x] 每请求一个异步会话，事务在请求结束时提交或回滚并归还连接池；仓储层是业务代码访问数据的唯一入口
- [x] 使用 Alembic 管理 Schema：空库上执行迁移得到完整 Schema，重复执行无副作用；迁移历史纳入版本控制
- [x] 模型变更必须伴随迁移，迁移与模型定义一致（决策理由见 `docs/adr/0001-use-alembic-for-schema-migration.md`）
- [x] 契约文件独立于两侧实现；后端契约测试断言产出满足契约，前端契约测试断言能解析契约声明的全部形状
- [x] 后端与前端测试各自可用一条命令运行
