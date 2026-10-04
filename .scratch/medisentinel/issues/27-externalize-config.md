# 27: 配置外置（DB / 凭据 → `.env`）

**What to build:** 把 `server/core/config.py` 里仍硬编码的口令、key 与生产连接串
外置到环境变量（`.env`）。配置来源改变，行为不变：测试注入自己的连接串，真实进程
缺 `DATABASE_URL` 时报明确错误，而不是静默用错默认值。

**Blocked by:** 25（`OPENAI_API_KEY` 已外置，本票沿用同一模式）

**Status:** in-progress

**背景：** 025 已处理 `openai_api_key`（空默认 + `.env`），但 `database_url`
等字段仍硬编码，且工作区有未提交的口令改动（`123456→root`）。

**范围：**

1. 先读 `server/core/config.py`，报告所有字段的当前定义：
   - 哪些是硬编码敏感值（口令、key、连接串）
   - 哪些是普通默认值（可保留）
   - 逐一列出「字段名 / 当前默认 / 是否敏感」
2. 读 `server/.env.example`，报告已有变量。
3. 对敏感字段（至少 `database_url`）：
   - 默认值改为空串或明确的非敏感占位
   - 若连接串必须由 env 提供，缺失时给出明确报错（不是静默用错默认）
   - 保留 pydantic-settings 自动读 env / `.env` 的行为
4. 更新 `server/.env.example`，补上 `DATABASE_URL` 等敏感字段（名 + 空值 + 注释）。
5. 更新 README 的「快速启动」段：说明必须自建 `.env` 并填哪些变量。
6. 处理工作区未提交的 `config.py` 改动（口令 `123456→root`）：
   该改动正是要清理的硬编码，一并改掉，不单独提交这个中间状态。
7. 加测试：断言 `config.py` 源码或 `Settings` 默认值不含具体口令、不含具体 API
   key（正则扫描，防回归）。

**验收清单：**

- [ ] `config.py` 无硬编码口令 / key / 生产连接串
- [ ] `.env.example` 列出全部必填变量（名 + 空 + 注释）
- [ ] README 说明 `.env` 建法
- [ ] 测试：默认值不含敏感字面串
- [ ] 既有测试全绿（配置来源变了，但行为不变）
- [ ] ticket Comments 记录：哪些字段外置了、用户需在自己的 `.env` 补什么

**边界：**

- 不改业务逻辑
- 不改 schema、不新增迁移
- 不做前端（028 起）
- 不改 001–026 的行为

**重要（用户本地 `.env` 要补）：** 改完后，用户自己的 `server/.env` 需要补
`DATABASE_URL`（和已存在的 `OPENAI_*` 并列）；确切行写入 Comments 与最终报告。

## Comments
