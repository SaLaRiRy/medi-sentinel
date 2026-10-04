# 27: 配置外置（DB / 凭据 → `.env`）

**What to build:** 把 `server/core/config.py` 里仍硬编码的口令、key 与生产连接串
外置到环境变量（`.env`）。配置来源改变，行为不变：测试注入自己的连接串，真实进程
缺 `DATABASE_URL` 时报明确错误，而不是静默用错默认值。

**Blocked by:** 25（`OPENAI_API_KEY` 已外置，本票沿用同一模式）

**Status:** done
Completed: 7761e1f

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

- [x] `config.py` 无硬编码口令 / key / 生产连接串
- [x] `.env.example` 列出全部必填变量（名 + 空 + 注释）
- [x] README 说明 `.env` 建法
- [x] 测试：默认值不含敏感字面串
- [x] 既有测试全绿（配置来源变了，但行为不变）
- [x] ticket Comments 记录：哪些字段外置了、用户需在自己的 `.env` 补什么

**边界：**

- 不改业务逻辑
- 不改 schema、不新增迁移
- 不做前端（028 起）
- 不改 001–026 的行为

**重要（用户本地 `.env` 要补）：** 改完后，用户自己的 `server/.env` 需要补
`DATABASE_URL`（和已存在的 `OPENAI_*` 并列）；确切行写入 Comments 与最终报告。

## Comments

### 交付物

| 文件 | 说明 |
|---|---|
| `server/core/config.py` | `database_url` / `neo4j_password` / `jwt_secret_key` 默认值改为空串（普通默认值保留）；新增 `env_ignore_empty=True` |
| `server/db/session.py` | `Database` 构造期对空连接串抛 `ValueError`（含 `DATABASE_URL`），不再静默用错默认 |
| `server/.env.example` | 补 `DATABASE_URL` / `NEO4J_*` / `JWT_SECRET_KEY`（名 + 空值 + 注释），沿用「留空 = 用默认」契约 |
| `README.md` | 「启动方式 / 后端」改为「复制 `.env.example` 为 `.env` 并填写」；架构段「配置」说明同步更新 |
| `server/tests/test_config_externalization.py` | 11 条防回归测试（源码正则扫描 + 默认值断言 + 空串报错 + 空 env 不覆盖默认） |

### 1. 字段清单（字段名 / 外置前默认 / 是否敏感）

| 字段名 | 外置前默认 | 是否敏感 |
|---|---|---|
| `project_name` | `"MediSentinel"` | 否 |
| `version` | `"0.1.0"` | 否 |
| `api_prefix` | `"/api/v1"` | 否 |
| `database_url` | `HEAD`: `mysql+aiomysql://root:123456@127.0.0.1:3306/medi_sentinel`；工作区未提交改动为 `root:root` | **是**（口令 + 生产连接串） |
| `neo4j_uri` | `"bolt://127.0.0.1:7687"` | 否（端点） |
| `neo4j_user` | `"neo4j"` | 否（用户名） |
| `neo4j_password` | `"12345678"` | **是**（口令） |
| `chroma_persist_dir` | `"chroma_db"` | 否 |
| `chroma_collection` | `"medical_knowledge"` | 否 |
| `openai_api_key` | `""`（025 已外置） | **是**（key，已空） |
| `openai_base_url` | `"https://dashscope.aliyuncs.com/compatible-mode/v1"` | 否（公共端点） |
| `llm_model` | `"qwen3.8-flash"` | 否 |
| `embedding_model` | `"text-embedding-v4"` | 否 |
| `embedding_dimensions` | `2048` | 否 |
| `embedding_batch_size` | `10` | 否 |
| `chunk_size` / `chunk_overlap` / `retrieval_top_k` | `500` / `80` / `5` | 否 |
| `jwt_secret_key` | `"medi-sentinel-jwt-secret"` | **是**（签名密钥） |
| `jwt_algorithm` | `"HS256"` | 否 |
| `jwt_expire_minutes` | `1440` | 否 |
| `upload_dir` / `uploads_url_prefix` / `avatar_subdir` / `avatar_max_bytes` | `"D:/uploads33"` / `"/uploads33"` / `"avatar"` / `2*1024*1024` | 否 |
| `knowledge_subdir` / `knowledge_max_bytes` | `"knowledge"` / `10*1024*1024` | 否 |
| `event_loop_block_threshold_ms` | `250` | 否 |
| `cors_allow_origins` / `cors_allow_credentials` | `["*"]` / `True` | 否 |

### 2. `.env.example` 已有变量（外置前）

`OPENAI_API_KEY` / `OPENAI_BASE_URL` / `LLM_MODEL` / `EMBEDDING_MODEL` —— 均为空值占位。

### 3. 本票外置的字段（默认值 → 空串，由 env / `.env` 提供）

- `database_url`：`mysql+aiomysql://root:root@127.0.0.1:3306/medi_sentinel` → `""`
- `neo4j_password`：`"12345678"` → `""`
- `jwt_secret_key`：`"medi-sentinel-jwt-secret"` → `""`

保留的普通默认：`neo4j_uri` / `neo4j_user` / `openai_base_url` / `llm_model` /
`embedding_*` / 分块与检索参数 / 上传目录 / CORS 等（无凭据，可保留）。

### 4. 行为保持说明

- pydantic-settings 仍自动读 env / `.env`；新增 `env_ignore_empty=True`，使
  `.env.example` 里的空值不被当作「显式置空」而覆盖代码默认（否则 `NEO4J_URI=`
  会把端点置空）。所有既有测试与 `.env` 现状行为不变。
- `DATABASE_URL` 缺失（空串）时，`db.session.Database` 在构造期抛 `ValueError`
  （消息含 `DATABASE_URL`），后端启动即失败，不再静默连旧默认库（ticket §3）。
- `build_llm` 的「无 key / base_url → `UnavailableLlmPort`」保持；图谱/向量适配器
  的懒连接与降级保持。
- 本票不改 schema、不新增迁移、不改前端、不改 001–026 业务行为；`config.py` 里
  未提交的 `123456→root` 中间改动已随本票一并重写，未单独提交。

### 5. 验证

- `pytest -q --basetemp=.tmp\pytest` → **851 passed, 1 skipped**（跳过的是
  `test_seed_demo_sql` 的 MySQL 集成项；基线 840 + 本票新增 11）。
- 新增 `server/tests/test_config_externalization.py`：正则扫描 `config.py` 源码不含
  历史口令 / key / 生产连接串；敏感字段默认值为空；`Database("")` 抛错；空 env
  不覆盖代码默认。

### 6. 用户需在自己的 `server/.env` 补的行（请手动加）

```dotenv
# 必填：你本地 MySQL 的连接串（留空则后端启动报 DATABASE_URL 未配置）
DATABASE_URL=mysql+aiomysql://root:<你的口令>@127.0.0.1:3306/medi_sentinel
# 建议：令牌签名密钥（自定义任意强随机串；留空可跑但不安全）
JWT_SECRET_KEY=<随机串>
# 需要图谱时补（不补则图谱支路降级）
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<你的图库口令>
```

原有的 `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `LLM_MODEL` 保持不变。本票不改动你
已存在的 `.env`（gitignored），只要求你补上以上行。

### 7. Standards 轴（fallback：subagent 通道投递失败，本地自查）

- 仓库无 `CODING_STANDARDS.md` / `CONTRIBUTING.md`；遵循 `AGENTS.md` 与
  issue-tracker 约定：ticket 位于 `.scratch/medisentinel/issues/27-*.md`、含
  `Status:` 行，测试置于 `server/tests/`，中文 docstring 与既有风格一致；改动文件
  均 ≤ 88 列、无行尾空白、无新增依赖。
- 判断项（Duplicated Code）：`mysql+aiomysql://...` 示例串在 `.env.example`、README、
  `db/session.py` 报错信息各出现一次。三处受众不同（样例 / 文档 / 运行期报错），
  不抽公共常量。
- 判断项（Duplicated Code）：测试里 `FORBIDDEN_LITERALS` 与 `MUST_BE_EMPTY_DEFAULTS`
  字段名有重叠，但前者防「源码出现具体值」、后者防「默认非空」，职责不同。
- 判断项（Primitive Obsession）：`database_url` 仍是 `str`，属仓库既有约定，超本票范围。
- 判断项（Divergent Change）：`config.py` 同时承载「默认值外置」与「env 解析策略
  （`env_ignore_empty`）」，同属配置职责，未拆分。

### 8. Spec 轴

- 覆盖 ticket 范围 1–7 与全部验收清单；未越界（未改 schema / 迁移 / 前端 / 001–026 行为）。
- 唯一新增运行期行为是「配置缺失时显式报错」，ticket §3 明确要求；有效配置路径行为不变。
- 说明：`SPEC.md` 7.1 原将「凭据硬编码」列为范围外，本票是用户显式要求的有意变更，
  覆盖该条。
