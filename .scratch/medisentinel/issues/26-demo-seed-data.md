# 26: 演示数据 `.sql`

**What to build:** 一份可直接加载的演示数据，让三角色账号打开各自主页就能看到东西：
患者有预约/档案/问诊，医生有待分配工单，管理员有数字。单文件
`server/seeds/demo_v1.sql`，DML-only（前置 `alembic upgrade head`），固定编号 +
upsert，可重复执行且不清空用户自建数据。向量数据（Chroma）不在本票，那是 013 的
`scripts/init_knowledge.py` 的职责。

**Blocked by:** 17、18、19、20、21、22（被演示的业务域）

**Status:** ready-for-agent

**覆盖范围（全部要）：** 用户（患者/医生/管理员）、科室、医生档案（关联科室）、
患者档案、预约挂号、健康档案、人工问诊工单 + 回复、健康科普文章 + 公告、
会话与消息（可选）。

**开工前必做（逐条给结论）：**

1. 读 `server/models/` 全部模型，确认表名、字段名、外键、NOT NULL 约束。
2. 读 `server/services/auth_service.py` 与 `server/core/security.py`，确认口令存储
   方式；演示口令必须能通过登录校验。
3. 确认目标库是 MySQL 还是 MariaDB，以及 `ON DUPLICATE KEY UPDATE` 是否兼容。
4. 查当前数据库实际状态（各表行数、是否已有用户自建数据、固定编号是否冲突）。

**验收清单：**

- [ ] `server/seeds/demo_v1.sql` 存在（或 sql + 脚本组合），DML-only，固定 ID + upsert
- [ ] 加载后：三角色账号可登录（口令写进本文件 Comments）
- [ ] 加载后：患者能看预约、档案、问诊；医生能看待分配工单；管理员能看统计有数字
- [ ] 重复执行两次，结果一致，无报错
- [ ] 一个验证测试（pytest 或独立脚本）：加载 sql → 断言关键表行数 + 关键外键成立
- [ ] ticket Comments 记录：演示账号清单、加载命令、已知限制

**边界：** 不动 001–025 的既有代码（除本 ticket 文件）；不改 schema、不新增迁移；
不引新依赖；不做向量数据；不做前端（027 起）。

**README（本票顺带）：** 「快速启动」段加一步「加载演示数据」；改掉
「骨架阶段，五个 Skill 尚未实现」的过期文案。

## Comments
