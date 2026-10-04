# 26: 演示数据 `.sql`

**What to build:** 一份可直接加载的演示数据，让三角色账号打开各自主页就能看到东西：
患者有预约/档案/问诊，医生有待分配工单，管理员有数字。单文件
`server/seeds/demo_v1.sql`，DML-only（前置 `alembic upgrade head`），固定编号 +
upsert，可重复执行且不清空用户自建数据。向量数据（Chroma）不在本票，那是 013 的
`scripts/init_knowledge.py` 的职责。

**Blocked by:** 17、18、19、20、21、22（被演示的业务域）

**Status:** done
Completed: 4954c38

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

- [x] `server/seeds/demo_v1.sql` 存在（或 sql + 脚本组合），DML-only，固定 ID + upsert
- [x] 加载后：三角色账号可登录（口令写进本文件 Comments）
- [x] 加载后：患者能看预约、档案、问诊；医生能看待分配工单；管理员能看统计有数字
- [x] 重复执行两次，结果一致，无报错
- [x] 一个验证测试（pytest 或独立脚本）：加载 sql → 断言关键表行数 + 关键外键成立
- [x] ticket Comments 记录：演示账号清单、加载命令、已知限制

**边界：** 不动 001–025 的既有代码（除本 ticket 文件）；不改 schema、不新增迁移；
不引新依赖；不做向量数据；不做前端（027 起）。

**README（本票顺带）：** 「快速启动」段加一步「加载演示数据」；改掉
「骨架阶段，五个 Skill 尚未实现」的过期文案。

## Comments

### 交付物

| 文件 | 说明 |
|---|---|
| `server/seeds/demo_v1.sql` | 单文件演示数据，DML-only，固定编号 9001+，`INSERT ... ON DUPLICATE KEY UPDATE` 幂等 upsert |
| `server/tests/test_seed_demo_sql.py` | 冒烟验证：静态断言（DML-only / 固定编号 / 口令可登录）+ MySQL 集成断言（连续加载两次、关键表行数、外键完整） |
| `README.md` | 「初始化数据」加「加载演示数据」一步；改掉「骨架阶段，五个 Skill 尚未实现」等过期文案 |

### 目录名与理由

单文件落在 `server/seeds/`（而非 `server/scripts/`）：`scripts/` 是可执行入口
（`init_graph.py` / `init_knowledge.py`），`seeds/` 是**纯数据**且按版本命名
（`demo_v1.sql`），后续新增数据集不挤进脚本目录。

### 开工前四条结论

1. **模型**：逐表确认表名与字段——`t_user` / `t_doctor` / `t_admin`（`username` 唯一、
   `password` 非空、`real_name`/`nickname` 命名不同）、`t_department`、`t_appointment`、
   `t_health_record`、`t_doctor_consult` / `t_doctor_reply`、`t_article` / `t_notice`、
   `t_consult_session` / `t_consult_message`。数据库层外键只有三处：
   `t_doctor_reply.consult_id → t_doctor_consult.id`、`t_consult_message.session_id →
   t_consult_session.id`、`t_knowledge_chunk.file_id → t_knowledge_file.id`；
   账号类引用（预约/档案/工单/医生科室）只建索引不建外键，由业务层保证。
2. **口令存储**：**明文**，非哈希。`core/security.py::verify_password` 直接
   `plain == stored`（`services/auth_service.py::login` 调它）。算法名：无；
   哈希样例：不适用；验证方式：`tests/test_seed_demo_sql.py` 用真实
   `verify_password("123456", stored)` 断言通过，且已在真实库上跑通三角色登录。
   因此**不需要** `server/scripts/seed_demo.py`，纯 SQL 即可。
3. **目标库**：**MySQL 8.0.39**（`database_url` 驱动 `mysql+aiomysql`；服务
   `MySQL80` 运行中），`ON DUPLICATE KEY UPDATE` 完全兼容，无需 MariaDB 分支或
   「先 DELETE 再 INSERT」替代。现代行别名写法 `VALUES ... AS seeded` 已在本机 8.0.39
   实测可用（避免 8.0.20 起对 `VALUES()` 的弃用告警）。
4. **当前库状态**（`medi_sentinel`，已 `alembic upgrade head` 到 `0011`）：
   `t_user`=1（id=1 `user01`）、`t_consult_session`=3（id 1–3，属 user 1）、
   `t_consult_message`=10、`t_knowledge_file`=3（id 1–3），其余表为 0。
   **存在用户自建数据**，故本文件固定编号取 `9001+` 段，与 1–3 不冲突；upsert 只碰
   这 30 条 9001+ 行，不清空、不覆盖其他行。

### 演示账号清单（口令写在这里，免得以后忘）

| 用户名 | 角色 | 口令 | 编号 | 展示名 |
|---|---|---|---|---|
| `patient1` | 患者 `user` | `123456` | 9001 | 张三 |
| `patient2` | 患者 `user` | `123456` | 9002 | 李四 |
| `patient3` | 患者 `user` | `123456` | 9003 | 王五 |
| `doctor1` | 医生 `doctor` | `123456` | 9001 | 陈医生（内科） |
| `doctor2` | 医生 `doctor` | `123456` | 9002 | 刘医生（外科） |
| `doctor3` | 医生 `doctor` | `123456` | 9003 | 赵医生（儿科） |
| `admin1` | 管理员 `admin` | `123456` | 9001 | 系统管理员 |

口令为明文（见结论 2），`PasswordChangeRequest` 等既有逻辑不受影响。

### 加载命令

```powershell
cd server
alembic upgrade head
# Windows 下必须带 charset 参数，否则中文按本地代码页发送、报 Incorrect string value
mysql --default-character-set=utf8mb4 -uroot -p medi_sentinel < seeds\demo_v1.sql
```

### 验证结果（真机）

- 后端套件：`pytest -q --basetemp=.tmp\pytest` → **840 passed**（836 基线 + 4 新增）。
- 集成验证：`tests/test_seed_demo_sql.py` 在一次性 schema
  `medi_sentinel_demo_seedcheck` 上 `alembic upgrade head` 后连续加载两次，
  15 项行数/外键断言全过，两次结果一致，验证完即删库。
- 真实加载：`mysql ... < seeds\demo_v1.sql` 连跑两次均 exit 0；真实库端到端冒烟
  三角色登录并访问各自页面：患者 `appointments/my`=2、`records/my`=1、`consults/my`=2；
  医生 `consults/pending`=1；管理员 `stat/overview` =
  `{user_count:4, doctor_count:3, session_count:5, appointment_count:3,
  knowledge_count:3, article_count:3}`（历史 1 患者 + 3 会话 + 3 知识文件在列）。

### 已知限制

- `t_consult_session.user_id` 与账号类引用一样无外键，属业务层约定。
- 若某个 9001+ 用户名已被既有数据占用，MySQL 会按**唯一键**更新那一行而不是新建
  9001 号行；此时以既有行为准（文件头已注明）。
- 只覆盖关系库；知识库分块与向量化（Chroma）仍由 `scripts/init_knowledge.py` 负责。
- 日期是固定字面量，医生工作台「今日预约」不会自动落在当天。

### Standards 轴（fallback：subagent 通道投递失败，本地自查）

- 无文档化标准硬违规：仓库无 `CODING_STANDARDS.md`/`CONTRIBUTING.md`；适用
  `AGENTS.md` 与 issue-tracker 约定。issue 文件位置/命名、`Status:` 行、测试文件命名、
  中文模块 docstring 与既有风格一致；新 Python 文件行宽 ≤88、无尾随空格、无新增依赖。
- 判断项 1（Primitive Obsession / 魔法数）：固定编号 `9001` 在 SQL 与测试里重复出现。
  这是「可重复执行的演示数据」的核心约定，已在文件头与测试 docstring 写明来源，
  不引入额外类型。
- 判断项 2（测试里重复 SQL 解析）：`_statements()` 与两条正则都基于同一约定
  （无分号字面量、全角逗号）。属该票自包含的轻量解析，非通用 SQL 解析器，
  已在 docstring 说明前提。
- 判断项 3（Speculative Generality）：`CHECK_SCHEMA` / `COUNT_QUERIES` 只服务本票断言，
  无多余配置钩子。
- 判断项 4（长行）：`server/seeds/demo_v1.sql` 的 `VALUES` 行最长约 200 字符。仓库
  未规定 SQL 行宽，且行长写保证「一行一条记录」便于审阅与 upsert 就地替换，保留。
- 判断项 5（README 顺带改动）：除本票点名的过期句子外，还改了技术栈一行的
  「LangChain 异步调用」→ httpx（025 已落地真实适配器，属同类过期文案）。

### Spec 轴

- 覆盖范围全部落地：三角色账号、科室、医生档案（关联科室）、患者档案、预约、
  健康档案、人工问诊工单 + 回复、文章 + 公告、会话 + 消息；每条验收清单项都有可执行
  断言（静态 3 条 + 集成 1 条 + 真机端到端冒烟）。
- 无范围蔓延：未建表、未新增迁移、未引依赖、未做 Chroma 向量数据、未动前端、
  未改 001–025 既有代码（仅新增本 ticket 文件与 README 文案）。
- 说明：验收要求「三角色账号可登录」以两条证据覆盖——测试里用真实
  `verify_password` 断言口令可过登录校验，真机上再跑一次真实 `POST /auth/login`
  并访问各自页面。
