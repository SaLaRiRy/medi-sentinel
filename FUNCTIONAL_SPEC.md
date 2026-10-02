# AI 智能医疗问诊平台 —— 功能规格说明书

> **文档性质**：本文档由通读现有源码得出，描述**代码当前的实际行为**，不是设想中的设计。
> **技术栈约定**：第 1–5 章以角色化名称描述各组件（关系型数据库、图数据库、向量索引、嵌入模型、大模型服务、前端单页应用），不出现具体产品名与版本；具体产品集中在**第 6 章**。
> **阅读约定**：正文中文；代码标识符、文件路径、字段名、枚举值、接口路径保留原文不翻译。`文件:行号` 指向行为出处。
> **不含内容**：本文档不含任何升级、重构、迁移或改进建议。
>
> **与原始描述的已知差异**：需求描述的核心链路顺序为「症状提取 → 图谱查询 → 向量检索」，代码实现为「向量检索 → 症状提取 → 图谱推理」。第 3 章以**目标流程 / 现状流程**对照形式记录，并以代码实际顺序为准。

---

## 目录

- [第 1 章　整体目录结构与模块划分](#第-1-章整体目录结构与模块划分)
- [第 2 章　模块职责、关键函数与对外接口](#第-2-章模块职责关键函数与对外接口)
- [第 3 章　核心数据流](#第-3-章核心数据流)
- [第 4 章　数据模型（实体、字段、关系）](#第-4-章数据模型实体字段关系)
- [第 5 章　业务规则](#第-5-章业务规则)
- [第 6 章　外部依赖](#第-6-章外部依赖)
- [附录 A　术语表](#附录-a术语表)
- [附录 B　现状事实与边界](#附录-b现状事实与边界)

---

## 第 1 章　整体目录结构与模块划分

### 1.1 顶层结构

工程根目录只有两个子目录，前后端分离，无共享代码、无统一构建：

```
ai-medical-platform/
├── server/          服务端应用
└── client/          前端单页应用
```

### 1.2 服务端目录

```
server/
├── main.py                应用入口：应用装配、生命周期、跨域、异常处理、静态资源挂载
├── core/                  横切关注点
│   ├── config.py          全部配置常量与统一访问入口 settings
│   ├── deps.py            当前登录用户解析、角色守卫
│   ├── security.py        口令比对、访问令牌签发与解析
│   └── response.py        统一响应封装（成功 / 失败 / 分页）
├── db/
│   ├── base.py            模型基类再导出（无自有内容）
│   └── session.py         数据库连接定义与「每请求一个会话」的供给
├── models/                14 个实体的定义，分布于 7 个文件
│   ├── __init__.py        实体统一再导出
│   ├── admin.py           Admin
│   ├── user.py            User
│   ├── doctor.py          Doctor
│   ├── department.py      Department
│   ├── appointment.py     Appointment + HealthRecord
│   ├── consult.py         ConsultSession + ConsultMessage
│   ├── doctor_consult.py  DoctorConsult + DoctorReply
│   ├── article.py         Article + Notice
│   └── knowledge.py       KnowledgeFile + KnowledgeChunk
├── schemas/
│   └── common.py          全部请求体 / 响应体数据结构（364 行，无其他 schema 文件）
├── api/v1/                接口层，统一前缀 /api/v1，共 14 个路由模块
│   ├── __init__.py        路由汇总与各模块子前缀
│   ├── auth.py            认证          ├── chat.py         AI 问诊
│   ├── profile.py         个人中心      ├── graph.py        知识图谱
│   ├── user.py            用户管理      ├── consult.py      人工问诊
│   ├── doctor.py          医生管理      ├── appointment.py  预约挂号
│   ├── department.py      科室管理      ├── record.py       健康档案
│   ├── knowledge.py       知识库        ├── article.py      健康科普
│   ├── notice.py          系统公告      └── stat.py         数据统计
├── services/              领域服务层
│   ├── auth_service.py    三角色登录与患者注册
│   ├── rag_service.py     检索增强问答主流程 + 文件向量化
│   ├── graph_service.py   图数据库查询与症状推理
│   └── stat_service.py    各类统计聚合
├── rag/                   检索增强流水线（与 services 分离的纯管道层）
│   ├── loader.py          文档解析（按扩展名分派）
│   ├── splitter.py        文本分块
│   ├── embeddings.py      嵌入模型调用
│   └── vector_store.py    向量索引读写
├── utils/
│   ├── helpers.py         时间格式化、上传落盘、扩展名→类型映射
│   └── validation.py      参数校验错误的中文提示翻译
├── scripts/               初始化与迁移脚本（非服务运行时调用）
│   ├── init_graph.py      图数据库建库与灌数（633 行）
│   ├── init_knowledge.py  知识库种子文档灌入并向量化
│   ├── migrate_record_type.py  健康档案类型字段的一次性迁移
│   └── import_sql.py      关系库建表脚本导入
├── docs_seed/             3 篇中文医学种子文档
│   ├── 高血压防治指南.md
│   ├── 感冒与流感指南.md
│   └── 糖尿病健康管理.md
└── chroma_db/             向量索引的本地持久化目录（运行期生成）
```

### 1.3 前端目录

```
client/
├── index.html             入口页，标题「AI智能医疗问诊平台」
├── vite.config.js         开发服务器与代理配置、路径别名
├── package.json           依赖与脚本
└── src/
    ├── main.js            应用挂载：图标全局注册、状态仓库、路由、组件库（中文语言包）
    ├── App.vue            根组件（仅承载路由出口）
    ├── router/index.js    路由表 + 全局导航守卫（角色鉴权唯一落点）
    ├── layouts/
    │   ├── PortalLayout.vue  患者门户外壳（顶部导航 7 项）
    │   └── AdminLayout.vue   管理台 / 医生工作台共用外壳（侧边菜单按角色切换）
    ├── components/
    │   └── ProfilePanel.vue  三角色复用的个人资料与改密面板
    ├── stores/
    │   └── user.js        唯一的状态仓库：令牌、角色、用户信息与相关动作
    ├── utils/
    │   ├── request.js     请求客户端与两个拦截器
    │   └── format.js      头像地址、日期、列表数据、匹配度的格式化
    └── views/             28 个视图，按角色分区
        ├── auth/          Login、Register
        ├── portal/        Home、Chat、Symptom、Consult、Appointment、
        │                  Records、Articles、ArticleDetail、
        │                  NoticeDetail、Profile
        ├── doctor/        Dashboard、Consults、Appointments、Patients、Profile
        └── admin/         Dashboard、Users、Doctors、Departments、Knowledge、
                           Graph、Consults、Appointments、Articles、Notices、Profile
```

### 1.4 模块划分的两种视角

**按技术分层**（服务端）：

| 层 | 位置 | 职责 |
|---|---|---|
| 入口与横切层 | `main.py`、`core/` | 应用装配、配置、鉴权守卫、统一响应、异常归一 |
| 接口层 | `api/v1/` | 73 个 HTTP 端点，只做参数装配、权限声明与响应封装 |
| 服务层 | `services/` | 领域逻辑：认证、检索增强问答、图谱推理、统计 |
| 管道层 | `rag/` | 与业务无关的文档处理与向量读写四步管道 |
| 数据层 | `db/`、`models/` | 连接供给与 14 个实体定义 |
| 工具层 | `utils/` | 时间/文件/校验提示等无状态函数 |
| 运维脚本层 | `scripts/` | 建库、灌数、迁移，与请求链路完全解耦 |

**按业务域**（前后端合看）：

| 业务域 | 服务端模块 | 前端视图 |
|---|---|---|
| 认证与个人中心 | `auth.py`、`profile.py` | `auth/*`、`*/Profile.vue` |
| AI 智能问诊 | `chat.py`、`services/rag_service.py`、`rag/*` | `portal/Chat.vue` |
| 知识图谱与症状推理 | `graph.py`、`services/graph_service.py` | `portal/Symptom.vue`、`admin/Graph.vue` |
| 人工问诊 | `consult.py` | `portal/Consult.vue`、`doctor/Consults.vue`、`admin/Consults.vue` |
| 预约挂号 | `appointment.py` | `portal/Appointment.vue`、`doctor/Appointments.vue`、`admin/Appointments.vue` |
| 健康档案 | `record.py` | `portal/Records.vue`、`doctor/Patients.vue` |
| 知识库管理 | `knowledge.py` | `admin/Knowledge.vue` |
| 医患与科室主数据 | `user.py`、`doctor.py`、`department.py` | `admin/Users.vue`、`admin/Doctors.vue`、`admin/Departments.vue` |
| 健康科普与公告 | `article.py`、`notice.py` | `portal/Articles.vue`、`portal/NoticeDetail.vue`、`admin/Articles.vue`、`admin/Notices.vue` |
| 数据统计 | `stat.py`、`services/stat_service.py` | `admin/Dashboard.vue`、`doctor/Dashboard.vue`、`portal/Home.vue` |

### 1.5 规模

| 项 | 数量 |
|---|---|
| 服务端源码 | 54 个文件，约 3 718 行（不含虚拟环境与缓存） |
| 其中图数据库灌数脚本 | 633 行（占服务端约 17%） |
| 前端源码 | 39 个文件，约 6 102 行 |
| 前端视图 | 28 个 |
| HTTP 端点 | 73 个（含根路径） |
| 实体 | 14 个 |
| 图数据库节点标签 | 6 个；关系类型 7 个 |

---

## 第 2 章　模块职责、关键函数与对外接口

### 2.1 应用装配与横切模块

**位置**：`server/main.py`、`server/core/`

**职责**：装配应用对象；启动时创建必要目录；统一跨域策略；把框架异常与参数校验异常归一为同一种响应结构；挂载上传目录为静态资源。

**关键函数 / 对象**

| 名称 | 位置 | 行为 |
|---|---|---|
| `lifespan(app)` | `main.py:16-26` | 启动时依次创建上传根目录、`knowledge` 子目录、`avatar` 子目录、向量索引持久化目录；打印就绪与密钥缺失警告；无停机清理逻辑 |
| `http_exception_handler` | `main.py:37-50` | 把业务异常的 `detail` 归一为 `{"code": 状态码, "message": 文本, "data": null}`，`detail` 为列表时以全角分号连接 |
| `validation_exception_handler` | `main.py:53-60` | 参数校验失败统一返回 422 与中文提示 |
| `root()` | `main.py:78-81` | 根路径返回欢迎语与文档地址（不套统一响应外壳） |
| `success / error / page_result` | `core/response.py:5-22` | 统一响应构造：`{code, message, data}`；分页把 `{items, total, page, page_size}` 放入 `data` |
| `Settings` / `settings` | `core/config.py:54-79` | 全部配置的唯一访问入口；24 个配置项，其中仅大模型密钥来自环境变量 |

**对外接口**：无独立端点。应用的跨域策略为 `allow_origins=["*"]`、`allow_credentials=True`、`allow_methods=["*"]`、`allow_headers=["*"]`（`main.py:62-68`）。上传目录挂载于 URL 前缀 `/uploads33`，仅当该目录已存在时挂载（`main.py:71-72`）。

**统一响应外壳**

| 场景 | HTTP 状态 | 响应体 |
|---|---|---|
| 业务成功 | 200 | `{"code": 200, "message": <提示>, "data": <载荷>}` |
| 分页成功 | 200 | `{"code": 200, "message": "操作成功", "data": {"items": [...], "total": n, "page": p, "page_size": s}}` |
| 业务失败（`error()` 直返） | **200** | `{"code": 400, "message": <提示>, "data": null}` |
| 抛出的业务异常 | 401 / 403 / 404 等 | `{"code": <同状态码>, "message": <提示>, "data": null}` |
| 参数校验失败 | 422 | `{"code": 422, "message": <中文提示>}` |
| SSE 流式问答 | 200 | 非 JSON 外壳，`text/event-stream` |

> 注意：`error()` 直接返回时 HTTP 状态仍是 200，客户端必须依据响应体里的 `code` 判断成败；只有抛出异常才会产生非 200 状态。

### 2.2 认证与授权模块

**位置**：`server/core/security.py`、`server/core/deps.py`、`server/services/auth_service.py`、`server/api/v1/auth.py`、`server/api/v1/profile.py`

**职责**：三角色登录（管理员 / 医生 / 患者）与患者自助注册；访问令牌签发与解析；把令牌解析为「当前用户」；按角色放行接口；个人资料的读写与头像上传。

**关键函数**

| 名称 | 位置 | 行为 |
|---|---|---|
| `verify_password(plain, stored)` | `core/security.py:10-17` | 直接字符串相等比较，不做任何变换 |
| `create_access_token(data)` | `core/security.py:20-30` | 载荷加入 `exp`，有效期 1 440 分钟（24 小时） |
| `decode_access_token(token)` | `core/security.py:33-43` | 解析失败返回 `None`，不抛异常 |
| `CurrentUser` | `core/deps.py:17-24` | 携带 `user_id`、`username`、`role`、`obj`（该角色的实体行） |
| `get_current_user` | `core/deps.py:27-52` | 无凭证 → 401「未登录」；令牌无效 → 401「令牌无效或已过期」；载荷缺 `user_id`/`role` → 401「令牌数据不完整」；按角色到对应表取行，取不到 → 401「用户不存在」 |
| `require_roles(*roles)` | `core/deps.py:55-62` | 角色不在允许集合内 → 403「权限不足」 |
| `AuthService.login` | `services/auth_service.py:16-51` | 角色必须为 `admin`/`doctor`/`user`，否则 400「无效的角色类型」；按角色只查对应表；用户名或口令不符 → 401「用户名或密码错误」；状态为 0 → 403「账号已被禁用」 |
| `AuthService.register` | `services/auth_service.py:53-80` | 两次口令不一致 → 400；用户名已存在 → 400；新建患者性别强制为 1，状态取默认 1 |

**角色模型**：角色字符串为 `user`（患者）、`doctor`（医生）、`admin`（管理员）。系统**没有角色字段**：登录请求自带 `role`，它决定查哪张表，并写入令牌的 `role` 声明；之后每个请求都由该声明决定再次查哪张表。因此**同一用户名可在三张表中并存**，由登录时选择的角色区分。

**令牌**：以 `Authorization: Bearer <token>` 传递。载荷为 `sub`（用户名）、`user_id`、`role`、`exp`。

**对外接口**

| 方法 | 完整路径 | 角色 | 说明 |
|---|---|---|---|
| POST | `/api/v1/auth/login` | 公开 | 三角色登录，返回令牌与展示信息 |
| POST | `/api/v1/auth/register` | 公开 | 患者注册，角色固定为 `user` |
| GET | `/api/v1/profile/info` | 任意已登录 | 返回本人资料（字段按角色不同） |
| PUT | `/api/v1/profile/update` | 任意已登录 | 更新本人资料 |
| PUT | `/api/v1/profile/password` | 任意已登录 | 修改本人密码；原密码错误时以 200 外壳返回提示 |
| POST | `/api/v1/profile/avatar` | 任意已登录 | 上传头像（`multipart/form-data`，字段名 `file`） |

> 个人中心四个端点均无 id 参数，操作对象恒为令牌对应的本人（`profile.py:22, 51, 75, 88`），因此不存在越权访问他人资料的可表达路径。

### 2.3 检索增强问答模块

**位置**：`server/api/v1/chat.py`、`server/services/rag_service.py`、`server/rag/*`

**职责**：把用户自然语言问题，经向量检索与图谱推理组装为上下文，交给大模型流式生成回答；把回答、引用来源、图谱结果与耗时落库；同时承担知识库文件的解析、分块与向量化。

**关键函数**

| 名称 | 位置 | 行为 |
|---|---|---|
| `RagService.__init__` | `services/rag_service.py:35-44` | 构造大模型客户端（流式、温度 0.7），持有向量索引与图谱服务单例 |
| `RagService.process_file` | `services/rag_service.py:46-92` | 向量化一个知识文件：状态置「处理中」→ 解析 → 分块 → 清除旧分块与旧向量 → 写新分块 → 批量写入向量索引 → 记录块数、状态置「已向量化」；任一环节异常则状态置「失败」并抛出 |
| `RagService._extract_symptoms` | `services/rag_service.py:94-102` | 以固定 30 词表对用户原问做子串包含匹配，返回命中的症状词 |
| `RagService._build_context` | `services/rag_service.py:104-161` | 先向量检索、后图谱推理，把两者拼成一段上下文文本，返回 `(context, references, graph_results)` |
| `RagService.chat_stream` | `services/rag_service.py:163-227` | 组装提示词 → 逐块流式产出 SSE 帧 → 末尾产出汇总帧 |
| `get_rag_service` | `services/rag_service.py:230-237` | 进程内单例 |
| `load_document` | `rag/loader.py:6-20` | 按扩展名分派；`.txt/.md/.markdown` 走文本、`.pdf` 走 PDF、`.doc/.docx` 走 Word，其余抛「不支持的文件类型」 |
| `_load_text` | `rag/loader.py:23-31` | 依次尝试 `utf-8 → gbk → gb2312 → latin-1` 解码 |
| `split_text` | `rag/splitter.py:6-17` | 递归字符分块，块长 500、重叠 80，分隔符优先级 `["\n\n", "\n", "。", "！", "？", "；", " ", ""]` |
| `AlibabaEmbeddings.embed_documents / embed_query` | `rag/embeddings.py:24-55` | 按批（每批 10 条）调用嵌入服务，空文本替换为单空格 |
| `VectorStore.add_documents / search / delete_by_file_id` | `rag/vector_store.py:25-74` | 分批写入；查询返回 `content`、`metadata`、`distance`；按文件号删除 |
| `_vectorize_task` | `api/v1/knowledge.py:17-26` | 后台任务包装，独立开启数据库会话执行向量化 |

**对外接口**

| 方法 | 完整路径 | 角色 | 说明 |
|---|---|---|---|
| GET | `/api/v1/chat/sessions` | `user` | 本人会话列表，按更新时间倒序 |
| GET | `/api/v1/chat/sessions/{session_id}/messages` | `user` | 指定会话的消息（仅按会话号过滤） |
| POST | `/api/v1/chat/send` | `user` | 流式问答主体，SSE |
| GET | `/api/v1/chat/admin/sessions` | `admin` | 全部会话分页（页码与页长无上下界约束） |
| GET | `/api/v1/knowledge/list` | `admin` | 知识文件分页，可按文件名或类型模糊搜索 |
| POST | `/api/v1/knowledge/upload` | `admin` | 上传并异步向量化 |
| POST | `/api/v1/knowledge/{file_id}/revectorize` | `admin` | 重新向量化 |
| DELETE | `/api/v1/knowledge/{file_id}` | `admin` | 删文件 + 删分块 + 删向量 + 删磁盘文件 |

**SSE 帧协议**（`Content-Type: text/event-stream`，每帧 `data: <JSON>\n\n`）

| 帧类型 | 载荷字段 | 时机 |
|---|---|---|
| `session` | `session_id` | 流的第 1 帧，用于前端关联新建会话 |
| `content` | `content` | 每个生成片段一帧 |
| `done` | `references`、`graph`、`cost_time` | 生成结束，携带引用来源、图谱结果与总耗时 |
| `error` | `message` | 生成过程抛异常时 |

### 2.4 知识图谱模块

**位置**：`server/services/graph_service.py`、`server/api/v1/graph.py`、`server/scripts/init_graph.py`

**职责**：维护医学本体（疾病、症状、科室、药物、检查、食物）；由症状反查可能疾病并排序；提供疾病详情子图、实体邻域子图、全图与统计，供前端可视化。

**关键函数**

| 名称 | 位置 | 行为 |
|---|---|---|
| `SYMPTOM_ALIASES` | `services/graph_service.py:11-34` | 22 条口语化症状→标准症状的映射表 |
| `_normalize_symptoms` | `services/graph_service.py:46-55` | 去空白、查别名表、去重且保持输入顺序 |
| `infer_diseases_by_symptoms` | `services/graph_service.py:57-89` | 反向遍历「疾病-有症状-症状」关系，按命中症状数降序取前 10，并计算 `probability` |
| `get_disease_detail` | `services/graph_service.py:91-128` | 一次取回疾病的症状、科室、药物、检查、并发症、宜吃、忌吃；`description` 与 `treatment` 缺失时分别用「建议检查：…」「常用药物：…」兜底 |
| `get_entity_subgraph` | `services/graph_service.py:130-163` | 取某实体一跳邻居，**上限 30 条关系** |
| `search_entities` | `services/graph_service.py:165-174` | 按名称包含匹配，上限 20 条 |
| `get_full_graph` | `services/graph_service.py:176-200` | 返回全部有向关系，**无上限** |
| `get_graph_stats` | `services/graph_service.py:202-210` | 按标签统计节点数，降序 |
| `get_graph_service` | `services/graph_service.py:213-221` | 进程内单例 |
| `init_graph` | `scripts/init_graph.py` | 建 6 个唯一性约束 + 灌入 60 条疾病及其关联 |

**对外接口**

| 方法 | 完整路径 | 角色 | 说明 |
|---|---|---|---|
| POST | `/api/v1/graph/infer` | `user` / `doctor` / `admin` | 由症状列表推理可能疾病 |
| GET | `/api/v1/graph/disease/{name}` | **公开** | 疾病详情子图 |
| GET | `/api/v1/graph/full` | **公开** | 完整图谱，用于可视化 |
| GET | `/api/v1/graph/subgraph` | **公开** | 实体邻域子图，必填查询参数 `entity` |
| GET | `/api/v1/graph/search` | **公开** | 实体搜索，必填查询参数 `keyword` |
| GET | `/api/v1/graph/stats` | `admin` | 按标签的节点计数 |

### 2.5 医患主数据模块

**职责**：患者、医生、科室三类主数据的增删改查与启停；删除时手工级联清理关联业务数据。

| 模块 | 关键函数（位置） | 行为要点 |
|---|---|---|
| 用户管理 `api/v1/user.py` | `list_users`(34)、`create_user`(56)、`update_user`(84)、`delete_user`(118)、`update_status`(162) | 创建校验用户名唯一与两次口令一致；更新时口令仅在被提供时变更；删除为手工级联 |
| 医生管理 `api/v1/doctor.py` | `list_doctors`(36)、`admin_list_doctors`(57)、`create_doctor`(81)、`update_doctor`(111)、`delete_doctor`(148)、`update_status`(180) | 公开列表只显示状态为 1 且已分配科室的医生；管理列表显示全部状态 |
| 科室管理 `api/v1/department.py` | `list_departments`(41)、`admin_list`(50)、`create_department`(77)、`update_department`(93)、`delete_department`(112) | 名称唯一（应用层校验，非数据库约束）；公开列表只显示状态为 1，按 `sort_order` 升序；`doctor_count` 只统计已分配科室且状态为 1 的医生 |

**对外接口**

| 方法 | 完整路径 | 角色 |
|---|---|---|
| GET | `/api/v1/users/list` | `admin` |
| POST | `/api/v1/users/create` | `admin` |
| PUT | `/api/v1/users/{user_id}` | `admin` |
| DELETE | `/api/v1/users/{user_id}` | `admin` |
| PUT | `/api/v1/users/{user_id}/status`（`status` 走查询参数） | `admin` |
| GET | `/api/v1/doctors/list` | **公开** |
| GET | `/api/v1/doctors/admin/list` | `admin` |
| POST | `/api/v1/doctors/create` | `admin` |
| PUT | `/api/v1/doctors/{doctor_id}` | `admin` |
| DELETE | `/api/v1/doctors/{doctor_id}` | `admin` |
| PUT | `/api/v1/doctors/{doctor_id}/status` | `admin` |
| GET | `/api/v1/departments/list` | **公开** |
| GET | `/api/v1/departments/admin/list` | `admin` |
| POST | `/api/v1/departments/create` | `admin` |
| PUT | `/api/v1/departments/{dept_id}` | `admin` |
| DELETE | `/api/v1/departments/{dept_id}` | `admin` |

### 2.6 人工问诊模块

**职责**：患者提交图文问诊工单；医生领取并回复；管理员总览与清理。

| 关键函数 | 位置 | 行为要点 |
|---|---|---|
| `create_consult` | `api/v1/consult.py:18` | 可指定医生，也可留空成为「待分配」工单 |
| `my_consults` | `api/v1/consult.py:27` | 本人工单及全部回复；医生名为空时显示「待分配」 |
| `doctor_pending` | `api/v1/consult.py:44` | 过滤条件为「指派给我 **或** 尚未指派」且状态为 0 |
| `reply_consult` | `api/v1/consult.py:59` | 工单原无医生时由当前医生认领；追加回复并把状态置 1 |
| `admin_list` / `admin_delete` | `api/v1/consult.py:74`、`113` | 分页支持状态过滤；删除前先删该工单全部回复 |

**对外接口**

| 方法 | 完整路径 | 角色 |
|---|---|---|
| POST | `/api/v1/consult/create` | `user` |
| GET | `/api/v1/consult/my` | `user` |
| GET | `/api/v1/consult/doctor/pending` | `doctor` |
| POST | `/api/v1/consult/reply` | `doctor` |
| GET | `/api/v1/consult/admin/list` | `admin` |
| DELETE | `/api/v1/consult/admin/{consult_id}` | `admin` |

### 2.7 预约挂号与健康档案模块

**职责**：患者自助预约并查看；医生查看本人预约、变更预约状态、维护患者档案；管理员总览与清理。

| 关键函数 | 位置 | 行为要点 |
|---|---|---|
| `create_appointment` | `api/v1/appointment.py:21` | 落库状态取默认 0；无重复预约校验、无号源容量校验 |
| `my_appointments` / `doctor_my` | `api/v1/appointment.py:34`、`41` | 分别按患者号、医生号过滤（医生号取令牌中的 `user_id`） |
| `admin_list` | `api/v1/appointment.py:48` | 支持关键字、科室、就诊日期、状态四维过滤 |
| `update_status` | `api/v1/appointment.py:101` | 直接写入请求给定的状态值；记录不存在时仍返回成功 |
| `my_records` | `api/v1/record.py:18` | 患者查看本人档案 |
| `doctor_patients` | `api/v1/record.py:25` | 只返回由本人创建的档案 |
| `doctor_patient_options` | `api/v1/record.py:32` | 可选患者 = 该医生名下的预约人 ∪ 问诊人 ∪ 已建档人，去重 |
| `create/update/delete_record` | `api/v1/record.py:49`、`74`、`103` | 更新与删除同时以档案号与医生号过滤，不匹配则返回「档案不存在或无权限」 |

**对外接口**

| 方法 | 完整路径 | 角色 |
|---|---|---|
| POST | `/api/v1/appointments/create` | `user` |
| GET | `/api/v1/appointments/my` | `user` |
| GET | `/api/v1/appointments/doctor/my` | `doctor` |
| GET | `/api/v1/appointments/admin/list` | `admin` |
| DELETE | `/api/v1/appointments/admin/{appt_id}` | `admin` |
| PUT | `/api/v1/appointments/{appt_id}/status` | `admin` / `doctor` |
| GET | `/api/v1/records/my` | `user` |
| GET | `/api/v1/records/doctor/patients` | `doctor` |
| GET | `/api/v1/records/doctor/patient-options` | `doctor` |
| POST | `/api/v1/records/doctor/create` | `doctor` |
| PUT | `/api/v1/records/doctor/{record_id}` | `doctor` |
| DELETE | `/api/v1/records/doctor/{record_id}` | `doctor` |

### 2.8 内容与公告模块

**职责**：健康科普文章与系统公告的发布、下架、检索与阅读。两者均为**独立实体，与任何其他实体无关联**。

| 行为要点 | 位置 |
|---|---|
| 文章公开列表只返回状态为 1 的记录 | `api/v1/article.py:18` |
| 文章详情每次访问把浏览量加 1 并提交 | `api/v1/article.py:62-64` |
| 公告公开列表不分页，返回全部已发布公告 | `api/v1/notice.py:18` |
| 公告详情只返回状态为 1 的记录，否则 `data` 为 `null` | `api/v1/notice.py:52` |
| 文章与公告的更新、删除不做存在性校验，恒返回成功 | `article.py:81, 95`；`notice.py:70, 87` |

**对外接口**

| 方法 | 完整路径 | 角色 |
|---|---|---|
| GET | `/api/v1/articles/list` | **公开** |
| GET | `/api/v1/articles/{article_id}` | **公开** |
| GET | `/api/v1/articles/admin/list` | `admin` |
| POST | `/api/v1/articles/create` | `admin` |
| PUT | `/api/v1/articles/{article_id}` | `admin` |
| DELETE | `/api/v1/articles/{article_id}` | `admin` |
| GET | `/api/v1/notices/list` | **公开** |
| GET | `/api/v1/notices/{notice_id}` | **公开** |
| GET | `/api/v1/notices/admin/list` | `admin` |
| POST | `/api/v1/notices/create` | `admin` |
| PUT | `/api/v1/notices/{notice_id}` | `admin` |
| DELETE | `/api/v1/notices/{notice_id}` | `admin` |

### 2.9 统计模块

**位置**：`server/services/stat_service.py`、`server/api/v1/stat.py`

| 关键函数 | 位置 | 计算内容 |
|---|---|---|
| `overview` | `stat_service.py:18-28` | 患者、医生、AI 会话、预约、知识文件、文章六项总数 |
| `doctor_overview` | `stat_service.py:30-61` | `pending_consults`（指派给我或待分配且未回复）、`today_appointments`（就诊日期为今天）、`replied_consults`、`total_patients`（本人档案 ∪ 预约 ∪ 问诊的患者去重数） |
| `user_overview` | `stat_service.py:63-79` | 本人的人工问诊、预约、健康档案、AI 会话四项计数 |
| `consult_trend` | `stat_service.py:81-91` | 最近 N 个自然日各自新建的 AI 会话数，按日期升序 |
| `appointment_by_department` | `stat_service.py:93-101` | 每个科室的预约数，无预约的科室计 0 |
| `user_growth` | `stat_service.py:103-113` | 最近 N 个自然日各自新增患者数 |
| `knowledge_type_distribution` | `stat_service.py:115-122` | 按文件类型统计知识文件数 |

**对外接口**

| 方法 | 完整路径 | 角色 | 参数 |
|---|---|---|---|
| GET | `/api/v1/stat/overview` | `admin` / `doctor` | 无（按角色返回不同字段） |
| GET | `/api/v1/stat/user-overview` | `user` | 无 |
| GET | `/api/v1/stat/consult-trend` | `admin` | `days`，默认 7 |
| GET | `/api/v1/stat/appointment-dept` | `admin` | 无 |
| GET | `/api/v1/stat/user-growth` | `admin` | `days`，默认 7 |
| GET | `/api/v1/stat/knowledge-type` | `admin` | 无 |

### 2.10 工具与校验模块

| 名称 | 位置 | 行为 |
|---|---|---|
| `format_datetime` / `format_date` | `utils/helpers.py:8-19` | 空值返回 `None`；否则 `YYYY-MM-DD HH:MM:SS` / `YYYY-MM-DD` |
| `save_upload_file` | `utils/helpers.py:22-37` | 落盘为「随机 32 位十六进制 + 原扩展名」，返回 `/uploads33[/子目录]/文件名` |
| `get_file_type` | `utils/helpers.py:40-44` | 扩展名映射：`.txt→txt`、`.md→markdown`、`.pdf→pdf`、`.doc/.docx→doc`，其余 `unknown` |
| `FIELD_LABELS` | `utils/validation.py:4-24` | 19 个字段名的中文标签 |
| `translate_validation_error` | `utils/validation.py:32-80` | 把校验错误类型翻译为中文（过短、过长、缺失、非整数、越界、格式不符） |
| `format_validation_errors` | `utils/validation.py:83-96` | 多条错误去重后以全角分号连接 |

### 2.11 数据访问模块

| 名称 | 位置 | 行为 |
|---|---|---|
| 模型基类 | `db/base.py` | 仅再导出共享基类，无自有内容 |
| 连接定义 | `db/session.py:7-12` | 单一数据库连接；使用前探活；连接 3600 秒回收；不自动提交 |
| `get_db` | `db/session.py:18-24` | 每请求一个数据库会话，请求结束必关闭 |
| 实体再导出 | `models/__init__.py:2-10` | 统一导出 14 个实体 |

### 2.12 前端模块

**职责**：三角色各自的界面外壳与 28 个业务视图；路由级角色鉴权；统一的请求与错误处理；令牌与用户信息的本地持久化。

| 模块 | 位置 | 职责与要点 |
|---|---|---|
| 应用挂载 | `src/main.js` | 全局注册全部图标组件；安装状态仓库、路由、组件库（中文语言包） |
| 路由表 | `src/router/index.js` | 34 条路由记录（含 4 条重定向）；组件全部懒加载；`meta.public` 标记免登录、`meta.role` 标记角色、`meta.title` 供面包屑 |
| 导航守卫 | `src/router/index.js:98-133` | 唯一的鉴权落点，四步判定（见第 5.12 节） |
| 患者门户外壳 | `src/layouts/PortalLayout.vue` | 固定 7 项顶部导航；下拉菜单含个人中心与安全退出 |
| 管理台外壳 | `src/layouts/AdminLayout.vue` | 管理台与医生工作台共用；侧边菜单按角色切换（管理员 10 项 / 医生 4 项）；面包屑取 `meta.title` |
| 个人面板 | `src/components/ProfilePanel.vue` | 三角色复用的资料编辑与改密；按角色渲染不同字段组 |
| 状态仓库 | `src/stores/user.js` | `token`、`role`、`userInfo` 三个状态；`login`/`logout`/`clearAuth`/`setUserInfo`/`fetchProfile` |
| 请求层 | `src/utils/request.js` | 基础地址 `/api/v1`、超时 60 秒；请求拦截器附加令牌；响应拦截器拆壳与统一报错 |
| 格式化 | `src/utils/format.js` | 头像地址、日期时间、列表数据取用、匹配度百分比 |

**路由与角色对照**

| 分区 | 路径前缀 | 外壳 | 角色 | 视图数 |
|---|---|---|---|---|
| 认证 | `/login`、`/register` | 无 | 公开 | 2 |
| 患者门户 | `/portal/*` | PortalLayout | `user` | 11 |
| 医生工作台 | `/doctor/*` | AdminLayout | `doctor` | 5 |
| 管理后台 | `/admin/*` | AdminLayout | `admin` | 11 |

---

## 第 3 章　核心数据流

### 3.1 目标流程与现状流程对照

| 环节 | 需求描述的顺序 | 代码实际顺序 | 差异性质 |
|---|---|---|---|
| 1 | 用户输入 | 用户输入 | 一致 |
| 2 | 症状提取 | **向量检索** | 顺序不同 |
| 3 | 图谱查询 | **症状提取** | 顺序不同 |
| 4 | 向量检索 | **图谱推理** | 顺序不同 |
| 5 | LLM 生成 | 上下文组装 | 一致 |
| 6 | 输出 | LLM 生成 | 一致 |
| 7 | — | SSE 输出与落库 | 补充 |

**两点必须澄清的结构性事实：**

1. **向量检索与图谱推理是并列的两条支路，不是串联的两级。** 两者各自独立产生结果，之后仅被拼接进同一段上下文文本（`services/rag_service.py:159`）。图谱结果不参与向量的筛选或重排，向量结果也不影响图谱的排序。

2. **在对话链路中，症状提取的触发条件极窄。** `_extract_symptoms`（`services/rag_service.py:94`）用固定 30 词表对用户原问做子串匹配；而别名表定义在 `graph_service.py:11`，只对**已经被提取出来的词**做归一化。两表交集只有一个词 —— `发烧`（既是词表成员，又是别名键）。因此 `头疼`、`肚子痛`、`没力气`、`拉肚子`、`嗓子痛` 等其余 21 个别名，在对话链路中永远不会被提取，也就永远走不到归一化。别名映射只在直接调用 `/api/v1/graph/infer`（前端「症状推理」页显式传入症状列表）时才完整生效。

### 3.2 现状流程：AI 智能问诊（`/portal/chat`）

```
用户输入自然语言
   │
   ▼
[前端] POST /api/v1/chat/send          ← 原生 fetch，手工附加 Bearer 令牌
   │  body: { session_id?, message }
   ▼
[服务端 chat.py:38]
   ├─ 定位或新建会话
   │     · 带 session_id 时按「会话号 + 本人」查找；找不到则新建（含「属于他人」的情形）
   │     · 新建标题 = 消息前 20 字符，超出部分以 "..." 结尾
   ├─ 保存用户消息（role="user"）
   ├─ 取本会话全部消息，作为历史时**排除最后一条**（即刚保存的这条）
   └─ 建立 SSE 流
         │
         ├─ 第 1 帧：{"type":"session","session_id":N}
         │
         ▼
   [RagService.chat_stream]
         │
         ├─ (A) 向量检索 ──────────────── rag_service.py:113
         │      · 查询文本 = 用户原始问题
         │      · 取相似度最近 5 条
         │      · 每条产出：引用项（文件名 + 正文前 200 字符）
         │                  上下文片段「[文档N] <整块正文>」
         │
         ├─ (B) 症状提取 ──────────────── rag_service.py:136
         │      · 30 词固定表，对原问做子串包含匹配
         │      · 无命中 → 跳过整条图谱支路（记录日志「未匹配到症状关键词」）
         │
         ├─ (C) 图谱推理（仅当 B 有命中）─ rag_service.py:141
         │      · 别名归一化 → 去重保序
         │      · 反向遍历「疾病-有症状-症状」，统计每病命中症状数
         │      · 按命中数降序，取前 10
         │      · 计算 probability = 命中数 / 归一化后症状总数，保留 2 位小数
         │      · 科室缺失时记 "-"
         │      · 上下文片段「知识图谱推理结果：…」**只取前 5 条**
         │
         ├─ (D) 上下文组装 ────────────── rag_service.py:159
         │      · 以空行连接 (A) 与 (C) 的片段
         │      · 两者皆空 → "暂无相关知识库内容。"
         │
         ├─ (E) 提示词组装 ────────────── rag_service.py:173-191
         │      · system：4 条医疗安全与风格约束（见 5.4 节）
         │      · 历史：最多取最近 6 条
         │      · user：参考知识 + 用户问题
         │
         ├─ (F) 大模型流式生成 ────────── rag_service.py:206
         │      · 温度 0.7，流式
         │      · 每个片段 → 帧 {"type":"content","content":"…"}
         │
         └─ (G) 汇总帧 ────────────────── rag_service.py:227
                {"type":"done", references, graph, cost_time}
         │
         ▼
[前端] 逐帧解析：session 记会话号 / content 增量渲染 Markdown / error 抛错
   │     渲染器：markdown-it；失败提示「抱歉，AI 回复出现异常，请稍后重试。」
   ▼
[服务端 chat.py:89-106] 流结束后**另开会话**落库
   ├─ 写入助手消息（role="assistant"，正文=累计全文）
   ├─ 存 references_json、graph_json、cost_time
   └─ 会话消息数 += 2
   │
   ▼
[前端] 流结束后重新拉取会话列表
```

**关键时序约束**：助手消息的落库发生在流**完全结束之后**，且使用一个独立于请求的数据库会话（`chat.py:90`）。若流中途异常，`error` 帧已发出，助手消息不会写入，而此前保存的用户消息会保留。

### 3.3 现状流程：症状推理（`/portal/symptom`）

与 3.2 完全独立的一条链路，**不经过向量检索，也不调用大模型**：

```
用户在标签框中逐个录入症状（重复项静默忽略）
   │
   ▼
[前端] POST /api/v1/graph/infer   body: { symptoms: [...] }
   ▼
[服务端] GraphService.infer_diseases_by_symptoms
   ├─ 别名归一化（22 条映射在此**完整生效**）
   ├─ 去重保序；归一化后为空 → 直接返回空列表
   ├─ 图数据库一次查询：命中症状数降序，取前 10
   └─ 逐条计算 probability、department、matched
   ▼
[前端] 表格展示：可能疾病 / 匹配度进度条 / 建议科室 / 详情
   └─ 点击详情 → GET /api/v1/graph/disease/{name} → 抽屉展示症状、
      药物、检查、并发症、宜吃、忌吃
```

### 3.4 现状流程：知识入库（管理员上传文件 → 可被检索）

```
管理员上传文件
   │
   ▼
[服务端 knowledge.py:56]
   ├─ 扩展名门禁：不支持的扩展名 → 直接返回「不支持的文件类型，仅支持 txt/doc/pdf/markdown」
   ├─ 原文件落盘，文件名改为「随机 32 位十六进制 + 原扩展名」
   ├─ 建知识文件记录（状态取默认 0「已上传」）
   └─ 投递后台任务，立即返回「上传成功，正在向量化处理」
         │
         ▼（后台）
   [RagService.process_file]
         ├─ 状态 → 1「处理中」
         ├─ 按扩展名解析为纯文本（文本类依次尝试 4 种编码）
         ├─ 分块：块长 500、重叠 80
         ├─ 清除该文件已有分块与已有向量
         ├─ 逐块建分块记录，向量编号 = file_{文件号}_chunk_{序号}
         ├─ 分批（每批 10 条）调用嵌入服务并写入向量索引
         ├─ 记录分块数，状态 → 2「已向量化」
         └─ 任一环节异常 → 状态 → 3「失败」并抛出
   │
   ▼
[前端 admin/Knowledge.vue] 只要存在状态 0 或 1 的行，每 3 秒静默轮询列表；
                          全部完成或组件卸载后停止轮询
```

### 3.5 现状流程：登录与鉴权

```
[前端] 提交用户名 / 口令 / 角色（三选一）
   ▼
POST /api/v1/auth/login
   ├─ 角色非法 → 400「无效的角色类型」
   ├─ 按角色只查对应表
   ├─ 口令不符或用户不存在 → 401「用户名或密码错误」
   ├─ 状态为 0 → 403「账号已被禁用」
   └─ 成功 → 返回令牌 + 角色 + 用户号 + 用户名 + 展示名 + 头像
   ▼
[前端] 令牌、角色、用户信息写入本地存储；按角色跳转各自首页
   ▼
后续每个请求：请求拦截器附加 Authorization: Bearer <令牌>
   ▼
[服务端] 解析令牌 → 取角色 → 查对应表 → 角色守卫比对
   ├─ 401 → 前端清除本地鉴权并跳转登录页
   └─ 403 → 仅弹出错误提示，不清除鉴权、不跳转
```

---

## 第 4 章　数据模型（实体、字段、关系）

### 4.1 通用约定

- 全部 14 个实体共用一个关系型数据库，字符集为 `utf8mb4`。
- 每个实体都有自增整数主键 `id`。
- 除 `ConsultMessage`、`DoctorReply`、`KnowledgeChunk` 外，每个实体都有 `create_time` 与 `update_time`；这三个只有 `create_time`。`create_time` 在插入时自动取当前时间，`update_time` 在插入时取当前时间并在每次修改时自动刷新。
- **没有任何实体声明外键。** 所有跨实体引用都是普通整数编号，数据库层不做任何约束；第 4.4 节所述级联删除全部由应用代码手工完成。
- 没有小数（金额）字段，没有布尔字段。启用/停用、发布/下架统一用整数 `1`/`0` 表达；"没有值"统一用空值表达，不用布尔。
- 带单位的字段只有 `file_size`（字节）与 `cost_time`（毫秒）。

### 4.2 实体清单

| 实体 | 表名 | 中文名 | 定义位置 |
|---|---|---|---|
| `Admin` | `t_admin` | 管理员 | `models/admin.py:6` |
| `User` | `t_user` | 患者用户 | `models/user.py:6` |
| `Doctor` | `t_doctor` | 医生 | `models/doctor.py:6` |
| `Department` | `t_department` | 科室 | `models/department.py:6` |
| `Appointment` | `t_appointment` | 预约挂号 | `models/appointment.py:6` |
| `HealthRecord` | `t_health_record` | 健康档案 | `models/appointment.py:23` |
| `ConsultSession` | `t_consult_session` | AI 问诊会话 | `models/consult.py:6` |
| `ConsultMessage` | `t_consult_message` | AI 问诊消息 | `models/consult.py:19` |
| `DoctorConsult` | `t_doctor_consult` | 人工问诊工单 | `models/doctor_consult.py:6` |
| `DoctorReply` | `t_doctor_reply` | 医生回复 | `models/doctor_consult.py:20` |
| `Article` | `t_article` | 健康科普文章 | `models/article.py:6` |
| `Notice` | `t_notice` | 系统公告 | `models/article.py:23` |
| `KnowledgeFile` | `t_knowledge_file` | 知识库文件 | `models/knowledge.py:6` |
| `KnowledgeChunk` | `t_knowledge_chunk` | 知识库分块 | `models/knowledge.py:24` |

### 4.3 字段明细

#### 4.3.1 Admin —— 管理员（`t_admin`）

| 字段 | 含义 | 类型 | 可空 | 默认 | 唯一 |
|---|---|---|---|---|---|
| `id` | 主键 | 整数 | 否 | 自增 | 主键 |
| `username` | 登录名 | 文本(50) | 否 | — | **唯一** |
| `password` | 口令 | 文本(100) | 否 | — | — |
| `nickname` | 昵称 | 文本(50) | 是 | — | — |
| `avatar` | 头像路径 | 文本(255) | 是 | — | — |
| `phone` | 手机号 | 文本(20) | 是 | — | — |
| `email` | 邮箱 | 文本(100) | 是 | — | — |
| `status` | 状态 | 整数枚举 | 是 | 1 | — |
| `create_time` / `update_time` | 创建 / 更新时间 | 时间 | 是 | 自动 | — |

#### 4.3.2 User —— 患者（`t_user`）

| 字段 | 含义 | 类型 | 可空 | 默认 | 唯一 |
|---|---|---|---|---|---|
| `id` | 主键 | 整数 | 否 | 自增 | 主键 |
| `username` | 登录名 | 文本(50) | 否 | — | **唯一** |
| `password` | 口令 | 文本(100) | 否 | — | — |
| `real_name` | 用户昵称 | 文本(50) | 是 | — | — |
| `gender` | 性别（1 男 / 2 女） | 整数枚举 | 是 | 1 | — |
| `age` | 年龄 | 整数 | 是 | — | — |
| `phone` | 手机号 | 文本(20) | 是 | — | — |
| `avatar` | 头像路径 | 文本(255) | 是 | — | — |
| `allergy_history` | 过敏史 | 长文本 | 是 | — | — |
| `status` | 状态 | 整数枚举 | 是 | 1 | — |
| `create_time` / `update_time` | 创建 / 更新时间 | 时间 | 是 | 自动 | — |

#### 4.3.3 Doctor —— 医生（`t_doctor`）

| 字段 | 含义 | 类型 | 可空 | 默认 | 唯一 |
|---|---|---|---|---|---|
| `id` | 主键 | 整数 | 否 | 自增 | 主键 |
| `username` | 登录账号 | 文本(50) | 否 | — | **唯一** |
| `password` | 口令 | 文本(100) | 否 | — | — |
| `real_name` | 医生姓名 | 文本(50) | 否 | — | — |
| `department_id` | 所属科室编号 | 整数 → `t_department.id` | 是 | — | — |
| `title` | 职称 | 文本(50) | 是 | — | — |
| `specialty` | 擅长领域 | 文本(255) | 是 | — | — |
| `introduction` | 个人简介 | 长文本 | 是 | — | — |
| `avatar` | 头像路径 | 文本(255) | 是 | — | — |
| `phone` | 手机号 | 文本(20) | 是 | — | — |
| `status` | 状态 | 整数枚举 | 是 | 1 | — |
| `create_time` / `update_time` | 创建 / 更新时间 | 时间 | 是 | 自动 | — |

> `title` 为自由文本，数据层不存在职称枚举。`department_id` 可空，即医生可以不属于任何科室；公开医生列表只展示状态为 1 且已分配科室的医生。

#### 4.3.4 Department —— 科室（`t_department`）

| 字段 | 含义 | 类型 | 可空 | 默认 | 唯一 |
|---|---|---|---|---|---|
| `id` | 主键 | 整数 | 否 | 自增 | 主键 |
| `name` | 科室名称 | 文本(50) | 否 | — | 无数据库约束，唯一性由应用层保证 |
| `description` | 科室描述 | 文本(255) | 是 | — | — |
| `sort_order` | 排序 | 整数 | 是 | 0 | — |
| `status` | 状态 | 整数枚举 | 是 | 1 | — |
| `create_time` / `update_time` | 创建 / 更新时间 | 时间 | 是 | 自动 | — |

#### 4.3.5 Appointment —— 预约挂号（`t_appointment`）

| 字段 | 含义 | 类型 | 可空 | 默认 | 唯一 |
|---|---|---|---|---|---|
| `id` | 主键 | 整数 | 否 | 自增 | 主键 |
| `user_id` | 患者编号 | 整数 → `t_user.id` | 否 | — | — |
| `doctor_id` | 医生编号 | 整数 → `t_doctor.id` | 否 | — | — |
| `department_id` | 科室编号 | 整数 → `t_department.id` | 否 | — | — |
| `visit_date` | 就诊日期 | 日期 | 否 | — | — |
| `time_slot` | 时段 | 文本(20) | 否 | — | — |
| `status` | 状态 | 整数枚举 | 是 | 0 | — |
| `remark` | 备注 | 文本(255) | 是 | — | — |
| `create_time` / `update_time` | 创建 / 更新时间 | 时间 | 是 | 自动 | — |

> `time_slot` 界面提供「上午 / 下午 / 晚上」，但字段为自由文本，不受校验。**不存在任何唯一性或号源容量约束**：同一患者可对同一医生、同一日期、同一时段重复预约无限次。

#### 4.3.6 HealthRecord —— 健康档案（`t_health_record`）

| 字段 | 含义 | 类型 | 可空 | 默认 | 唯一 |
|---|---|---|---|---|---|
| `id` | 主键 | 整数 | 否 | 自增 | 主键 |
| `user_id` | 患者编号 | 整数 → `t_user.id` | 否 | — | — |
| `doctor_id` | 医生编号 | 整数 → `t_doctor.id` | 是 | — | — |
| `record_type` | 档案类型 | 文本(50) | 是 | 模型无默认；迁移脚本回填「门诊记录」 | — |
| `diagnosis` | 诊断结果 | 文本(255) | 是 | — | — |
| `treatment` | 治疗方案 | 长文本 | 是 | — | — |
| `prescription` | 处方 | 长文本 | 是 | — | — |
| `visit_date` | 就诊日期 | 日期 | 是 | — | — |
| `create_time` / `update_time` | 创建 / 更新时间 | 时间 | 是 | 自动 | — |

> `record_type` 为自由文本，界面提供「门诊记录 / 住院记录 / 体检报告 / 复诊记录 / 其他」，表单默认「门诊记录」。`doctor_id` 为空表示该档案未归属到具体医生。

#### 4.3.7 ConsultSession —— AI 问诊会话（`t_consult_session`）

| 字段 | 含义 | 类型 | 可空 | 默认 | 唯一 |
|---|---|---|---|---|---|
| `id` | 主键 | 整数 | 否 | 自增 | 主键 |
| `user_id` | 患者编号 | 整数 → `t_user.id` | 否 | — | — |
| `title` | 会话标题 | 文本(200) | 是 | 「新会话」 | — |
| `message_count` | 消息数量 | 整数 | 是 | 0 | — |
| `create_time` / `update_time` | 创建 / 更新时间 | 时间 | 是 | 自动 | — |

> 标题由首条消息前 20 字符加省略号生成；`message_count` 每次问答加 2。

#### 4.3.8 ConsultMessage —— AI 问诊消息（`t_consult_message`）

| 字段 | 含义 | 类型 | 可空 | 默认 | 唯一 |
|---|---|---|---|---|---|
| `id` | 主键 | 整数 | 否 | 自增 | 主键 |
| `session_id` | 会话编号 | 整数 → `t_consult_session.id` | 否 | — | — |
| `role` | 说话方 | 文本(20) 枚举 | 否 | — | — |
| `content` | 消息正文 | 长文本 | 否 | — | — |
| `references_json` | 引用来源（JSON 文本） | 长文本 | 是 | — | — |
| `graph_json` | 图谱实体（JSON 文本） | 长文本 | 是 | — | — |
| `cost_time` | 生成耗时（毫秒） | 整数 | 是 | 0 | — |
| `create_time` | 创建时间 | 时间 | 是 | 自动 | — |

> `role` 取值：`user`（患者发言）、`assistant`（AI 回复）。`cost_time` 仅 AI 回复有值。

#### 4.3.9 DoctorConsult —— 人工问诊工单（`t_doctor_consult`）

| 字段 | 含义 | 类型 | 可空 | 默认 | 唯一 |
|---|---|---|---|---|---|
| `id` | 主键 | 整数 | 否 | 自增 | 主键 |
| `user_id` | 提问患者编号 | 整数 → `t_user.id` | 否 | — | — |
| `doctor_id` | 医生编号 | 整数 → `t_doctor.id` | 是 | — | — |
| `chief_complaint` | 主诉 | 长文本 | 否 | — | — |
| `status` | 状态 | 整数枚举 | 是 | 0 | — |
| `create_time` / `update_time` | 创建 / 更新时间 | 时间 | 是 | 自动 | — |

> `doctor_id` 为空表示「待分配」：工单对所有医生可见，由首位回复的医生认领。

#### 4.3.10 DoctorReply —— 医生回复（`t_doctor_reply`）

| 字段 | 含义 | 类型 | 可空 | 默认 | 唯一 |
|---|---|---|---|---|---|
| `id` | 主键 | 整数 | 否 | 自增 | 主键 |
| `consult_id` | 工单编号 | 整数 → `t_doctor_consult.id` | 否 | — | — |
| `doctor_id` | 回复医生编号 | 整数 → `t_doctor.id` | 否 | — | — |
| `content` | 回复内容 | 长文本 | 否 | — | — |
| `create_time` | 创建时间 | 时间 | 是 | 自动 | — |

> **无「一单一次回复」约束**：状态置为「已回复」后仍可继续追加回复，患者端按时间顺序全部展示。

#### 4.3.11 Article —— 健康科普文章（`t_article`）

| 字段 | 含义 | 类型 | 可空 | 默认 | 唯一 |
|---|---|---|---|---|---|
| `id` | 主键 | 整数 | 否 | 自增 | 主键 |
| `title` | 文章标题 | 文本(200) | 否 | — | 不唯一 |
| `category` | 分类 | 文本(50) | 是 | — | — |
| `cover` | 封面图 | 文本(255) | 是 | — | — |
| `summary` | 摘要 | 文本(500) | 是 | — | — |
| `content` | 文章正文 | 长文本 | 是 | — | — |
| `view_count` | 浏览量 | 整数 | 是 | 0 | — |
| `status` | 状态 | 整数枚举 | 是 | 1 | — |
| `create_time` / `update_time` | 创建 / 更新时间 | 时间 | 是 | 自动 | — |

> `category` 界面提供「健康科普 / 疾病预防 / 用药指南 / 营养饮食 / 运动康复 / 其他」，同时允许自由输入。

#### 4.3.12 Notice —— 系统公告（`t_notice`）

| 字段 | 含义 | 类型 | 可空 | 默认 | 唯一 |
|---|---|---|---|---|---|
| `id` | 主键 | 整数 | 否 | 自增 | 主键 |
| `title` | 公告标题 | 文本(200) | 否 | — | 不唯一 |
| `content` | 公告正文 | 长文本 | 是 | — | — |
| `status` | 状态 | 整数枚举 | 是 | 1 | — |
| `create_time` / `update_time` | 创建 / 更新时间 | 时间 | 是 | 自动 | — |

#### 4.3.13 KnowledgeFile —— 知识库文件（`t_knowledge_file`）

| 字段 | 含义 | 类型 | 可空 | 默认 | 唯一 |
|---|---|---|---|---|---|
| `id` | 主键 | 整数 | 否 | 自增 | 主键 |
| `file_name` | 文件名 | 文本(255) | 否 | — | 无数据库约束；灌数脚本以它作为业务键去重 |
| `file_type` | 文件类型 | 文本(20) 枚举 | 否 | — | — |
| `file_size` | 文件大小（字节） | 64 位整数 | 是 | 0 | — |
| `file_path` | 存储路径 | 文本(500) | 否 | — | — |
| `chunk_count` | 分块数量 | 整数 | 是 | 0 | — |
| `vector_status` | 向量化状态 | 整数枚举 | 是 | 0 | — |
| `upload_by` | 上传人编号 | 整数，按角色指向三张不同表 | 是 | — | — |
| `upload_role` | 上传人角色 | 文本(20) 枚举 | 是 | `admin` | — |
| `create_time` / `update_time` | 创建 / 更新时间 | 时间 | 是 | 自动 | — |

#### 4.3.14 KnowledgeChunk —— 知识库分块（`t_knowledge_chunk`）

| 字段 | 含义 | 类型 | 可空 | 默认 | 唯一 |
|---|---|---|---|---|---|
| `id` | 主键 | 整数 | 否 | 自增 | 主键 |
| `file_id` | 文件编号 | 整数 → `t_knowledge_file.id` | 否 | — | — |
| `chunk_index` | 分块序号 | 整数 | 否 | — | 无约束；同一文件序号不重复仅因重建前会先清空 |
| `content` | 分块正文 | 长文本 | 否 | — | — |
| `vector_id` | 向量编号 | 文本(100) | 是 | — | — |
| `create_time` | 创建时间 | 时间 | 是 | 自动 | — |

> `vector_id` 生成规则：`file_{文件号}_chunk_{分块序号}`，与向量索引中的标识一致。

### 4.4 关系全图

所有关系均为**逻辑关系**，数据库层无外键；下表右侧「删除影响」全部由应用代码手工实现。

```
Admin      独立实体，无任何关联

User ──1:N──▶ ConsultSession ──1:N──▶ ConsultMessage
  │
  ├──1:N──▶ DoctorConsult ──1:N──▶ DoctorReply
  │              ▲
  │              └──N:1(可空)── Doctor
  │
  ├──1:N──▶ Appointment ──N:1──▶ Doctor
  │             └──N:1──▶ Department
  │
  └──1:N──▶ HealthRecord ──N:1(可空)──▶ Doctor

Department ──1:N──▶ Doctor                    （医生侧可空）

KnowledgeFile ──1:N──▶ KnowledgeChunk
      └── upload_by + upload_role：按角色松散指向 Admin / Doctor / User

Article    独立实体，无任何关联
Notice     独立实体，无任何关联
```

| 关系 | 基数 | 可空侧 | 删除影响 |
|---|---|---|---|
| 患者 → AI 会话 | 1:N | — | 删患者时，先删其所有会话的全部消息，再删会话 |
| AI 会话 → 消息 | 1:N | — | 随会话删除；无单独删除入口 |
| 患者 → 人工问诊工单 | 1:N | — | 删患者时，先删工单的全部回复，再删工单 |
| 工单 → 医生回复 | 1:N | — | 随工单删除；删医生时也一并删除 |
| 医生 → 工单 | 0/1:N | 工单侧 | 删医生时删除指名该医生的工单；**未指派的工单不受影响，继续存在** |
| 医生 → 医生回复 | 1:N | — | 随医生删除 |
| 科室 → 医生 | 0/1:N | 医生侧 | 删除科室前先校验，**只要还有医生属于该科室则拒绝删除** |
| 患者 → 预约 | 1:N | — | 随患者删除 |
| 医生 → 预约 | 1:N | — | 随医生删除 |
| 科室 → 预约 | 1:N | — | **删除科室时不校验预约**，因此预约可能保留指向已删科室的编号 |
| 患者 → 健康档案 | 1:N | — | 随患者删除 |
| 医生 → 健康档案 | 0/1:N | 档案侧 | 随医生删除 |
| 知识文件 → 分块 | 1:N | — | 删文件时一并删除；重新向量化时先整体清空再重建 |
| 知识文件 → 上传人 | 松散 | — | 上传人信息（编号 + 角色）**不随上传人删除而清理** |
| 文章、公告 | 无 | — | 与其他实体无任何引用关系 |

### 4.5 唯一性约束

**数据库层声明的唯一性只有三处**，且各自限于本表：

- `t_admin.username`
- `t_user.username`
- `t_doctor.username`

由此得出：**同一登录名可以同时作为患者、医生、管理员存在**；登录时提交的角色字符串决定查哪张表，因此三者互不冲突。

**由应用层保证的唯一性**：

- 科室名称唯一：创建时校验，更新时排除自身后校验（`api/v1/department.py:83, 102`）。
- 知识文件名作为灌数脚本的业务键：同名文件跳过（`scripts/init_knowledge.py:23`）。
- 患者注册时预检用户名，抢先于数据库约束给出友好提示（`services/auth_service.py:60-62`）。

**不存在任何约束的地方**（重要）：每个医生每个时段只有一个号、一张工单只能回复一次、一次就诊只能建一份档案 —— 这些约束**均不存在**。此外，所有高频过滤字段（`user_id`、`doctor_id`、`department_id`、`status`、`visit_date`、`create_time`、`file_id`）**没有任何索引声明**。

---

## 第 5 章　业务规则

### 5.1 症状别名映射

**唯一来源**：`services/graph_service.py:11-34`，字典名 `SYMPTOM_ALIASES`，共 **22 条映射、14 个目标症状**。所有 14 个目标症状都存在于图数据库的 128 个症状节点中。

| 输入（口语） | 归一化为 | | 输入（口语） | 归一化为 |
|---|---|---|---|---|
| `头疼` | `头痛` | | `想吐` | `恶心` |
| `头胀` | `头痛` | | `拉肚子` | `腹泻` |
| `头昏` | `头晕` | | `关节疼` | `关节痛` |
| `发烧` | `发热` | | `腰疼` | `腰痛` |
| `发高烧` | `发热` | | `看不清` | `视力模糊` |
| `高烧` | `发热` | | `流鼻涕` | `流涕` |
| `低烧` | `发热` | | `喉咙痛` | `咽痛` |
| `肚子痛` | `腹痛` | | `嗓子痛` | `咽痛` |
| `胃疼` | `腹痛` | | `胸口痛` | `胸痛` |
| `胸口闷` | `胸闷` | | `没力气` | `乏力` |
| `疲倦` | `乏力` | | `疲劳` | `乏力` |

**归一化流程**：逐项去首尾空白 → 空串丢弃 → 查表替换（查不到则保留原词）→ 按输入顺序去重。

**生效边界（关键规则）**：别名表只对**已被提取出的症状词**生效。对话链路使用另一张独立的 30 词提取表（见 5.2），两张表的交集只有 `发烧` 一个词。因此：

- 经 `/api/v1/graph/infer` 传入症状（前端「症状推理」页）时，22 条映射**全部生效**。
- 经 `/api/v1/chat/send` 提问时，只有 `发烧` 可能触发别名归一化；其余 21 个别名因原词不在提取表中，永远无法进入归一化环节。

### 5.2 症状提取词表

**来源**：`services/rag_service.py:96-101` 硬编码，共 **30 个词**：

```
头痛  发热  咳嗽  乏力  恶心  呕吐  腹泻  腹痛
胸闷  心悸  头晕  失眠  皮疹  瘙痒  水肿  出血
关节痛 腰痛 视力模糊 耳鸣 鼻塞 咽痛 流涕
高血压 糖尿病 感冒 发烧 过敏 便秘 尿频
```

**匹配规则**：对用户原始问题做**子串包含**判断（`s in query`），不使用分词、不做同义词扩展、不做大小写或繁简处理。命中多个词时按词表顺序返回。未命中任何词时跳过整个图谱支路。

### 5.3 图谱推理与排序规则

**推理查询**（`services/graph_service.py:66-74`）语义：把归一化后的症状列表展开，逐个到症状节点，反向沿「疾病-有症状-症状」关系找到疾病，按疾病分组统计命中的症状个数，并按命中数降序取前 10 条。

**排序与打分规则**：

| 规则 | 值 |
|---|---|
| 排序键 | 命中症状数，降序 |
| 返回条数上限 | 10 |
| 打分公式 | `probability = 命中症状数 ÷ 归一化后症状总数`，四舍五入保留 2 位小数 |
| 最低命中阈值 | **无**。命中 1 个症状的疾病也会被返回 |
| 并列处理 | 未定义。同命中数的相对顺序由查询结果决定 |
| 科室缺失时的取值 | 字符串 `"-"` |
| 归一化后症状为空 | 直接返回空列表，不查询图数据库 |

**关于 `probability` 字段的语义澄清**：该值 = 命中数 ÷ **用户输入的症状总数**，衡量的是"用户所报症状中，有多少个能由该疾病解释"，是**覆盖率**，不是该疾病的患病概率。若用户输入 3 个症状而某疾病只关联其中 1 个，`probability` 为 0.33。前端「症状推理」页把它乘 100 后作为「匹配度」进度条展示。

**灌入上下文时的截断规则**：拼接进大模型上下文时，图谱结果**只取前 5 条**（`services/rag_service.py:153`），其余 5 条虽已算出但不进入提示词；它们仍会通过 `done` 帧完整回传给前端。

### 5.4 医疗安全提示词

**来源**：`services/rag_service.py:173-178`，系统提示词全文如下（4 条约束）：

```
你是AI智能医疗问诊助手，基于提供的知识库和医疗知识图谱为用户提供健康咨询。
请注意：
1. 你的回答仅供参考，不能替代专业医生的诊断
2. 如有严重症状，请建议用户及时就医
3. 结合知识库内容和图谱推理结果给出专业、易懂的建议
4. 回答要条理清晰，适当分点说明
```

**用户提示词模板**（`services/rag_service.py:180-185`）：

```
参考知识：
{context}

用户问题：{query}

请基于以上参考信息回答用户问题。
```

**消息组装规则**：系统提示词 1 条 + 历史消息**最多最近 6 条** + 当前用户提示词 1 条。历史中不含本次提问（历史来源已排除最后一条）。

**生成参数**：流式输出，温度 0.7。

**上下文兜底**：向量与图谱均无结果时，`context` 取固定文本「暂无相关知识库内容。」，模型仍会被调用。

### 5.5 检索增强参数规则

| 规则 | 值 | 来源 |
|---|---|---|
| 分块长度 | 500 字符 | `core/config.py:45` |
| 分块重叠 | 80 字符 | `core/config.py:46` |
| 分块分隔符优先级 | `\n\n` → `\n` → `。` → `！` → `？` → `；` → 空格 → 空串 | `rag/splitter.py:15` |
| 检索返回条数 | 5 | `core/config.py:47` |
| 相似度度量 | 余弦 | `rag/vector_store.py:21` |
| 向量维度 | 2048 | `core/config.py:29` |
| 嵌入批大小 | 10 | `core/config.py:30` |
| 向量集合名 | `medical_knowledge` | `core/config.py:37` |
| 引用项正文长度 | 前 200 字符 | `rag_service.py:130` |
| 空文本处理 | 替换为单个空格后再嵌入 | `rag/embeddings.py:32, 52` |
| 支持的文件扩展名 | `.txt`、`.md`、`.markdown`、`.pdf`、`.doc`、`.docx` | `rag/loader.py:12-20` |
| 文本类解码顺序 | `utf-8` → `gbk` → `gb2312` → `latin-1` | `rag/loader.py:25` |

### 5.6 知识库生命周期规则

**向量化状态机**（`KnowledgeFile.vector_status`）：

```
       上传
        │
        ▼
   0 已上传 ──▶ 1 处理中 ──▶ 2 已向量化
                    │
                    └────▶ 3 失败
```

**规则**：

- 上传时扩展名不在支持列表内 → **不入库**，直接返回「不支持的文件类型，仅支持 txt/doc/pdf/markdown」。
- 上传成功后状态取默认值 0，随后由后台任务处理；接口立即返回，不等待向量化。
- 重新向量化时，**先整体清除**该文件已有的分块记录与向量索引，再重建。
- 删除文件时，执行四步：删向量索引 → 删分块记录 → 删磁盘文件（存在时）→ 删文件记录。文件记录不存在时同样返回成功。
- 落盘文件名一律重命名为「随机 32 位十六进制 + 原扩展名」，与用户上传的原始名无关；原始名只保留在数据库字段中。

### 5.7 会话与消息规则

| 规则 | 值 |
|---|---|
| 会话标题生成 | 首条消息前 20 字符；超过 20 字符时在末尾追加 `...` |
| 会话归属校验 | 传入 `session_id` 时按「会话号 + 本人」查找；**不匹配（含属于他人）时不报错，改为新建会话** |
| 消息数计数 | 每次问答完成后 +2（用户 1 条 + 助手 1 条） |
| 历史消息范围 | 本会话全部消息，**排除最后一条**（即刚保存的用户消息） |
| 传入模型的历史条数 | 最多最近 6 条 |
| 助手消息落库时机 | 流**完全结束后**，使用独立的数据库会话 |
| 用户消息落库时机 | 调用模型**之前** |
| 流中途异常 | 不写入助手消息；已写入的用户消息保留 |
| 消息查询过滤 | 仅按会话号过滤，**不校验会话归属** |

### 5.8 认证、口令与角色规则

**口令规则**：

- 存储与比对均为**直接字符串相等**，不做任何变换（`core/security.py:10-17`）。
- 长度约束：注册、创建患者、创建医生均要求至少 6 位；修改密码接口无长度约束。

**令牌规则**：

| 项 | 值 |
|---|---|
| 算法 | `HS256` |
| 有效期 | 1 440 分钟（24 小时） |
| 签名密钥 | 配置文件内硬编码 |
| 载荷 | `sub`（用户名）、`user_id`、`role`、`exp` |
| 传递方式 | `Authorization: Bearer <令牌>` |
| 解析失败 | 返回 `None`，由调用方转为 401 |

**登录规则**：

| 情形 | 结果 |
|---|---|
| 角色不属于 `admin`/`doctor`/`user` | 400「无效的角色类型」 |
| 用户不存在或口令不符 | 401「用户名或密码错误」 |
| 账号状态为 0 | 403「账号已被禁用」 |
| 成功 | 返回令牌、角色、用户号、用户名、展示名、头像 |

**注册规则**：两次口令不一致 → 400；用户名已存在 → 400；性别强制为 1；角色固定为 `user`；**手机号与真实姓名无唯一性校验**。

**鉴权失败语义**：

| 状态 | 触发 | 前端表现 |
|---|---|---|
| 401 | 未登录 / 令牌过期 / 令牌载荷不完整 / 用户不存在 | 清除本地鉴权并跳转登录页 |
| 403 | 角色不匹配 | 仅弹出错误提示，**不清除鉴权、不跳转** |

### 5.9 参数校验规则

**通用事实**：**全系统没有任何正则表达式校验**。服务端与前端均无手机号、邮箱、身份证等格式校验。校验仅由「必填」与「长度」两类构成。

**长度与必填规则**：

| 场景 | 规则 |
|---|---|
| 患者注册 / 创建患者 | 用户名 3–50 字符；口令至少 6 字符 |
| 创建医生 | 用户名 3–50；姓名 1–50；口令至少 6 字符 |
| 修改口令（管理员改他人） | 提供了新口令但未填确认口令 → 400「请填写确认密码」；两者不一致 → 400「两次密码输入不一致」 |
| 发送问诊消息 | 正文至少 1 字符 |
| 分页参数 | 页码 ≥ 1；页长 1–100（**例外**：文章公开列表与 AI 会话管理列表的页码页长无任何约束） |
| 统计天数参数 | `days` 默认 7，无上下界约束 |

**中文错误提示生成规则**（`utils/validation.py`）：按字段名映射为中文标签；按错误类型套用固定句式（过短 → 「X至少N个字符」、过长 → 「X不能超过N个字符」、缺失 → 「请填写X」、非整数 → 「X必须为整数」、越界 → 「X不能小于/大于N」）；复合错误以全角分号连接并去重。未识别的字段名直接回退为原始英文字段名。

### 5.10 状态值与语义规则

**通用启用/发布状态**（`Admin`、`User`、`Doctor`、`Department`、`Article`、`Notice` 共用）：

| 值 | 含义 | 影响 |
|---|---|---|
| 1 | 正常 / 启用 / 已发布（默认） | 公开列表只返回状态为 1 的记录 |
| 0 | 禁用 / 隐藏 | 登录被拒（403「账号已被禁用」）；公开列表不可见 |

**预约状态**（`Appointment.status`，默认 0）：

| 值 | 含义 |
|---|---|
| 0 | 待确认（默认） |
| 1 | 已确认 |
| 2 | 已完成 |
| 3 | 已取消 |

**人工问诊工单状态**（`DoctorConsult.status`，默认 0）：

| 值 | 含义 |
|---|---|
| 0 | 待回复（默认） |
| 1 | 已回复（医生回复时自动置 1） |

**向量化状态**（`KnowledgeFile.vector_status`，默认 0）：

| 值 | 含义 |
|---|---|
| 0 | 已上传（默认，代码从不显式写入） |
| 1 | 处理中 |
| 2 | 已向量化 |
| 3 | 失败 |

**关键规则：不存在状态迁移校验。** 所有状态字段都直接写入请求给定的整数值。因此管理员可以把预约状态从「已完成」改回「待确认」，可以写入 4、5 等未定义值；`PUT /appointments/{id}/status` 在记录不存在时**仍返回「状态更新成功」**。

### 5.11 级联删除规则

**删除患者**（`api/v1/user.py:118-159`），执行顺序：

1. 删除该患者全部 AI 会话下的**所有消息**
2. 删除这些**会话**
3. 删除该患者全部人工问诊工单的**所有回复**
4. 删除这些**工单**
5. 删除该患者的**预约**
6. 删除该患者的**健康档案**
7. 删除**患者**

**删除医生**（`api/v1/doctor.py:148-177`），执行顺序：

1. 删除指名该医生的工单的**全部回复**
2. 删除指名该医生的**工单**
3. 删除指名该医生的**预约**
4. 删除指名该医生的**健康档案**
5. 删除**医生**

> **未指派的工单不在删除范围内**，会继续存在且保持「待分配」。

**没有删除入口的实体**：管理员只能通过状态接口停用，无删除路径；AI 会话与消息只能随患者删除；分块只能随文件删除。

### 5.12 科室删除保护规则

删除科室前统计属于该科室的医生数（`api/v1/department.py:117-119`）：

- 医生数 > 0 → 拒绝删除，提示「该科室下还有 N 位医生，无法删除」。
- 医生数 = 0 → 删除科室记录本身，**不重分配任何医生**。

**注意**：该保护**只校验医生，不校验预约**。因此科室可以被删除，而其名下预约记录仍保留指向该科室的编号（列表展示时科室名显示为空字符串）。

### 5.13 科室展示与排序规则

| 规则 | 内容 |
|---|---|
| 公开列表过滤 | 只返回状态为 1 的科室 |
| 公开列表排序 | 按 `sort_order` 升序；相同值按编号倒序（新的在前） |
| 医生数量统计口径 | **只统计已分配科室且状态为 1 的医生** |
| `sort_order` 缺省展示 | 空值显示为 0 |

### 5.14 人工问诊规则

| 规则 | 内容 |
|---|---|
| 工单可见性（医生端） | 指派给我 **或** 尚未指派，且状态为 0 |
| 抢单规则 | 工单原本无医生时，首位回复的医生即被写入为负责医生 |
| 回复后状态 | 无条件置为 1「已回复」 |
| 回复次数限制 | **无**。状态为 1 后仍可继续追加回复 |
| 回复归属校验 | 回复接口按工单号查找，**不校验该工单是否属于当前医生** |
| 医生名缺失展示 | 显示「待分配」 |
| 患者端展示 | 本人全部工单及其全部回复 |

### 5.15 主诉的前后端编码约定

前端将「标题 + 正文」编码为单个主诉字段，后端不作解析：

- 患者提交时：`chief_complaint = "标题：正文"`（使用**全角冒号**）。
- 医生端展示时：按**第一个**全角冒号拆回标题与正文；若无冒号，则整串作为标题、正文为空。

### 5.16 健康档案权限规则

| 操作 | 校验条件 | 不通过时 |
|---|---|---|
| 更新档案 | 档案号 **且** 医生号为当前医生 | 返回「档案不存在或无权限」 |
| 删除档案 | 档案号 **且** 医生号为当前医生 | 返回「档案不存在或无权限」 |
| 查询本人档案 | 患者号为当前患者 | 空列表 |
| 查询医生名下档案 | 医生号为当前医生 | 空列表 |
| 可选患者列表 | 该医生的预约人 ∪ 问诊人 ∪ 已建档人，去重 | 空列表 |

### 5.17 文章与公告规则

| 规则 | 内容 |
|---|---|
| 公开列表范围 | 只返回状态为 1 的记录 |
| 文章浏览量 | 每次打开详情 `+1` 并立即提交 |
| 公告公开列表 | **不分页**，一次返回全部已发布公告 |
| 公告详情范围 | 只返回状态为 1；未发布的返回 `data: null` |
| 更新/删除存在性 | **不校验**，恒返回成功 |
| 文章分类 | 界面提供 6 个建议值，同时允许自由输入 |

### 5.18 文件上传与静态资源规则

| 规则 | 内容 |
|---|---|
| 上传根目录 | `D:/uploads33` |
| 子目录 | 知识库文件 → `knowledge`；头像 → `avatar`；均于启动时自动创建 |
| 落盘命名 | 随机 32 位十六进制 + 原扩展名 |
| 静态访问前缀 | `/uploads33`，仅当该目录存在时挂载 |
| 头像地址拼装 | 前端：已是 `/uploads33` 开头或 `http` 开头则原样返回，否则补 `/uploads33/` 前缀 |
| 前端上传限制 | 知识库接受 `.txt,.pdf,.doc,.docx,.md`；头像接受 `image/*` |

### 5.19 前端校验规则

前端**不使用表单规则配置**，全部为提交时的命令式判断：

| 位置 | 规则 |
|---|---|
| 登录 | 用户名与口令均非空 |
| 注册 | 用户名与口令非空；两次口令一致 |
| 创建/编辑患者 | 用户名必填且去空白后 ≥ 3 字符；口令必填且 ≥ 6 字符；两次一致（编辑时仅在填写了新口令时校验） |
| 创建/编辑医生 | 用户名必填且 ≥ 3 字符；姓名必填；口令必填且 ≥ 6 字符；两次一致 |
| 创建科室 / 文章 / 公告 | 名称或标题必填 |
| 新增档案 | 必须选择患者与档案类型 |
| 回复工单 | 回复内容非空（去空白） |
| 发起咨询 | 医生、标题、内容均必填 |
| 新建预约 | 科室、医生、预约日期、时段均必填 |
| 症状推理 | 至少添加一个症状；重复标签静默忽略 |
| 修改密码 | 两次新口令一致 |

**前端输入限制**：患者用户名与医生用户名最长 50；手机号最长 20；年龄 1–150；科室名称最长 50、描述最长 255、排序 0–9999；文章标题最长 200、摘要最长 500、公告标题最长 200。日期选择器统一输出 `YYYY-MM-DD`。

### 5.20 前端状态展示映射规则

| 对象 | 映射 |
|---|---|
| 预约状态 | 0 待确认 / 1 已确认 / 2 已完成 / 3 已取消；未知值回退「待确认」；仅医生端着色（warning/success/info/danger） |
| 工单状态 | 1 → 已回复（success）；其余 → 待回复（warning） |
| 账号状态 | 1 → 正常（success）；其余 → 禁用（danger）；按钮文案随当前状态取反 |
| 文章 / 公告状态 | 1 → 已发布（success）；其余 → 已下架（info） |
| 向量化状态 | 0 已上传 / 1 处理中 / 2 已向量化 / 3 失败；轮询条件为状态 0 或 1，间隔 3 秒 |
| 性别 | 1 男 / 2 女；仅当值恰为 2 时视为女 |
| 图谱关系名 | `HAS_SYMPTOM` 有症状、`BELONGS_TO` 所属科室、`RECOMMEND_DRUG` 推荐药物、`NEED_CHECK` 需检查、`ACCOMPANY_WITH` 并发症、`SHOULD_EAT` 宜吃、`AVOID_EAT` 忌吃；未知关系显示原文 |
| 图谱节点类型 | `Disease` 疾病、`Symptom` 症状、`Department` 科室、`Drug` 药物、`Check` 检查、`Food` 食物；图例只分「疾病 / 症状 / 其他」三类 |
| 匹配度百分比 | 取 `probability`，值 ≤ 1 时乘 100；缺失时用「命中数 ÷ 输入症状数」现算 |

### 5.21 前端路由守卫规则

守卫是**唯一**的前端鉴权落点，按顺序四步判定：

1. 已登录但角色不在三角色映射表内 → 清除本地鉴权；目标为公开页则放行，否则跳登录页。
2. 目标标记为公开：已登录且目标为登录/注册页 → 跳该角色首页；否则放行。
3. 未登录 → 跳登录页。
4. 取路由匹配链中**最深的、声明了角色的**记录，与当前角色比对：不一致 → 跳当前角色首页（无映射则跳登录页）。

**补充规则**：

- 「已登录」的判定仅为**本地是否存在令牌**，不校验有效期，也不向服务端确认。
- 无 404 兜底路由。
- 侧边菜单按角色生成：管理员 10 项，医生 4 项；个人中心不在菜单中，只能从右上角下拉进入。
- 文章详情加载失败或记录不存在 → 跳回文章列表；公告详情同理跳回首页。
- 所有删除与状态变更操作均先弹确认框；取消或失败被静默吞掉。
- 列表加载失败时统一置空列表，界面呈现空状态而非错误状态。

---

## 第 6 章　外部依赖

> 本章是全文档**唯一**点名具体产品的章节。第 1–5 章一律使用角色化名称。

### 6.1 澄清一处表述

需求描述把「Vue 3」列为外部依赖。需要区分两类依赖：

- **外部服务**：独立进程或远程服务，需单独部署、单独运维，通过网络协议访问（关系型数据库、图数据库、大模型与嵌入服务）。
- **应用内库**：随应用一起打包运行的代码库，不构成独立服务（前端框架、组件库、图表库、HTTP 客户端）。

Vue 3 属于后者：它是前端单页应用的**运行时框架**，不是外部服务。下文按此分类。

### 6.2 外部服务依赖

| 服务 | 角色 | 具体产品与版本要求 | 用途 | 连接配置 |
|---|---|---|---|---|
| 关系型数据库 | 主数据存储 | MySQL，字符集 `utf8mb4`（驱动 `pymysql>=1.1.0`） | 存放全部 14 个实体：账号、主数据、预约、档案、会话消息、工单、内容、知识库元数据 | `127.0.0.1:3306`，库名 `db_ai_medical`；用户名、口令、主机、端口、库名**全部硬编码**于 `core/config.py:12-17` |
| 图数据库 | 医学知识图谱 | Neo4j（驱动 `neo4j>=5.0.0`），Bolt 协议 | 存放 6 类节点（疾病 144、症状 128、科室 20、药物 134、检查 94、食物 173，共 693 个）与 7 类关系（共 1 045 条）；支撑症状推理、疾病详情、全图可视化、实体搜索与统计 | `bolt://127.0.0.1:7687`；用户名 `neo4j`、口令**硬编码**于 `core/config.py:20-22` |
| 向量索引 | 语义检索 | Chroma（`chromadb>=0.5.0`），以**本地持久化模式**运行，非独立服务 | 存放知识库分块向量，供问答时做余弦相似度检索 | 持久化目录 `server/chroma_db`；集合名 `medical_knowledge`；相似度度量余弦 |
| 大模型服务 | 回答生成 | 兼容 OpenAI 接口的云端服务；当前配置 endpoint 为阿里云 MaaS 北京区兼容模式地址，模型标识 `qwen3.7-plus` | 基于知识库上下文与图谱结果流式生成健康咨询回答 | 地址硬编码；**密钥是唯一来自环境变量的配置项**（`OPENAI_API_KEY`） |
| 嵌入模型服务 | 文本向量化 | 同一兼容接口，模型标识 `text-embedding-v4`，输出 2048 维 | 把知识库分块与用户查询转为向量；批大小 10 | 同上 |

**说明**：

- 四类服务中，**只有密钥一项**可通过环境变量注入，其余连接参数全部写在源码常量中。密钥缺失时，启动阶段打印两次警告，服务照常启动，但问答与向量化在运行时失败。
- 图数据库与向量索引都缺少时会直接导致问答失败：图谱服务与向量存储在问答服务构造时即被实例化（`services/rag_service.py:43-44`）。

### 6.3 服务端应用内库

| 库 | 版本要求 | 用途 |
|---|---|---|
| `fastapi` | `>=0.109.0` | 接口框架：路由、依赖注入、请求校验、SSE 流式响应、静态资源挂载、跨域中间件 |
| `uvicorn[standard]` | `>=0.27.0` | 应用服务器 |
| `sqlalchemy` | `>=2.0.0` | 关系库访问与实体映射 |
| `pymysql` | `>=1.1.0` | MySQL 驱动 |
| `python-multipart` | `>=0.0.6` | 解析文件上传的表单数据 |
| `python-jose[cryptography]` | `>=3.3.0` | 访问令牌的签发与解析 |
| `langchain` / `-openai` / `-community` | `>=0.3.0` / `>=0.2.0` / `>=0.3.0` | 大模型客户端封装与流式调用 |
| `langchain-text-splitters` | `>=0.3.0` | 递归字符分块 |
| `chromadb` | `>=0.5.0` | 向量索引的本地持久化存储与检索 |
| `neo4j` | `>=5.0.0` | 图数据库驱动 |
| `pypdf` | `>=4.0.0` | PDF 文本抽取 |
| `python-docx` | `>=1.1.0` | Word 文档文本抽取 |
| `openai` | `>=1.0.0` | 嵌入接口的直接调用（嵌入未走 LangChain 封装） |

> `langchain` 与 `openai` 并存：大模型走前者，嵌入模型走后者，两者指向同一个兼容接口地址。

### 6.4 前端应用内库

| 库 | 版本 | 用途 |
|---|---|---|
| `vue` | `^3.5.39` | 界面框架；全部视图使用组合式 API |
| `vue-router` | `^4.5.0` | 路由、嵌套布局、路由元信息（公开/角色/标题）与全局导航守卫 |
| `pinia` | `^2.3.0` | 状态管理；唯一仓库 `user`，承载令牌、角色、用户信息 |
| `element-plus` | `^2.9.1` | 全部界面组件：布局、菜单、表格、表单、对话框、抽屉、分页、上传、日期选择等；同时提供消息提示与确认框服务；使用中文语言包 |
| `@element-plus/icons-vue` | `^2.3.1` | 图标集；全部图标在入口统一全局注册，模板中直接使用 |
| `axios` | `^1.7.9` | HTTP 客户端；承载基础地址、超时、请求与响应两个拦截器 |
| `echarts` | `^5.5.1` | 图表引擎；管理台数据概览（折线、饼图、柱状）与知识图谱力导向图 |
| `vue-echarts` | `^7.0.3` | 图表组件封装，在视图内以 `<v-chart>` 使用并自适应尺寸 |
| `markdown-it` | `^14.1.0` | 把 AI 回复的 Markdown 渲染为 HTML，在问答页以富文本展示 |

**前端构建依赖**：

| 库 | 版本 | 用途 |
|---|---|---|
| `vite` | `^8.1.1` | 开发服务器、生产构建、预览；开发服务器端口 5173 |
| `@vitejs/plugin-vue` | `^6.0.7` | 单文件组件编译 |

**开发期代理配置**（`vite.config.js:15-27`，仅开发环境生效）：

| 前缀 | 目标 | 用途 |
|---|---|---|
| `/api` | `http://127.0.0.1:8000` | 接口请求转发；**不做路径重写**，故 `/api/v1/...` 原样抵达后端 |
| `/uploads33` | `http://127.0.0.1:8000` | 头像与文件静态资源访问 |

**前端未引入的能力**（事实陈述）：无测试框架、无代码检查工具、无格式化工具、无 TypeScript、无 CSS 框架、无国际化库。`package.json` 仅含 `dev`、`build`、`preview` 三个脚本。

### 6.5 文件系统依赖

| 路径 | 用途 | 创建时机 |
|---|---|---|
| `D:/uploads33` | 上传文件根目录，同时被挂载为静态资源 | 应用启动时自动创建 |
| `D:/uploads33/knowledge` | 知识库文件 | 应用启动时自动创建 |
| `D:/uploads33/avatar` | 头像文件 | 应用启动时自动创建 |
| `server/chroma_db` | 向量索引持久化目录 | 应用启动时及向量存储初始化时创建 |
| `server/docs_seed` | 3 篇中文医学种子文档，供灌数脚本读取 | 随工程提交；目录不存在时脚本提示并退出 |

### 6.6 配置项全表

全部配置集中在 `core/config.py`，由 `Settings` 类统一暴露。**除密钥外均为硬编码常量**。

| 配置项 | 默认值 |
|---|---|
| `project_name` | `AI智能医疗问诊平台系统` |
| `database_url` | 由主机/端口/用户/口令/库名拼装（见 6.2） |
| `neo4j_uri` / `neo4j_user` / `neo4j_password` | `bolt://127.0.0.1:7687` / `neo4j` / 硬编码口令 |
| `openai_api_key` | **唯一环境变量** `OPENAI_API_KEY`，未设置时为空 |
| `openai_base_url` | 硬编码的云端兼容接口地址 |
| `llm_model` | `qwen3.7-plus` |
| `embedding_model` | `text-embedding-v4` |
| `embedding_dimensions` | `2048` |
| `embedding_batch_size` | `10` |
| `upload_dir` | `D:/uploads33` |
| `chroma_persist_dir` | `server/chroma_db` |
| `chroma_collection` | `medical_knowledge` |
| `jwt_secret_key` | 硬编码字符串 |
| `jwt_algorithm` | `HS256` |
| `jwt_expire_minutes` | `1440` |
| `chunk_size` | `500` |
| `chunk_overlap` | `80` |
| `retrieval_top_k` | `5` |

### 6.7 运维脚本依赖

| 脚本 | 依赖 | 说明 |
|---|---|---|
| `scripts/init_graph.py` | 图数据库 | 幂等：全部使用「不存在才创建」与「合并」语义，重复执行不新增、不删除；约束创建失败被静默忽略。一次执行发出 1 051 条语句（6 条约束 + 1 045 条合并） |
| `scripts/init_knowledge.py` | 关系库 + 向量索引 + 嵌入服务 | 幂等：按文件名跳过已存在记录；逐篇灌入并立即向量化，单篇失败不中断循环 |
| `scripts/migrate_record_type.py` | 关系库（直连） | 一次性迁移：字段不存在则新增并把空值回填为「门诊记录」；已存在则不做任何变更 |
| `scripts/import_sql.py` | 关系库（直连） | 导入建表脚本。**目标文件 `server/sql/db_ai_medical.sql` 在当前工程中不存在，该目录也不存在**，因此按现状执行会读取失败 |

---

## 附录 A　术语表

| 术语 | 定义 |
|---|---|
| **症状（Symptom）** | 患者主观不适的标准化名称，是图谱的独立节点类型，也是症状推理的入口概念。共 128 个。 |
| **疾病（Disease）** | 图谱的核心节点类型，其入边来自症状、出边指向科室、药物、检查、并发症与饮食建议。共 144 个（含 60 个主疾病与 84 个仅作为并发症出现、无其他关系的节点）。 |
| **科室（Department）** | 临床科室，既是图谱节点（20 个），也是主数据实体（用于医生归属与预约）。二者是两套独立数据，不自动同步。 |
| **主疾病与并发症节点** | 主疾病指灌数时带有完整关联（科室、症状、药物、检查、饮食）的 60 个疾病；并发症节点指仅因被「并发于」关系指向而创建的 84 个节点，它们只有名称，没有任何其他关联。 |
| **症状别名归一化** | 把患者口语表达（如「头疼」）转换为图谱标准名称（「头痛」）的过程，仅在症状已被提取出来之后适用。 |
| **症状提取** | 用固定 30 词表对用户原问做子串匹配，得到症状词列表的过程。与别名归一化是**两个独立环节**，词表也不相同。 |
| **命中数（match_count）** | 某个疾病关联的症状中，有多少个出现在本次输入的症状集合里。 |
| **`probability` 字段** | 值 = 命中数 ÷ 输入症状总数，四舍五入保留 2 位。语义上是**覆盖率**（输入症状被该疾病解释的比例），**不是患病概率**。前端把它展示为「匹配度」。 |
| **参考文献 / 引用来源（references）** | 向量检索命中的知识库分块摘要，每项含序号、文件名与正文前 200 字符，随结束帧回传前端。 |
| **知识库文件（KnowledgeFile）** | 上传的医学文档记录，携带向量化状态与分块数量。 |
| **分块（KnowledgeChunk）** | 知识库文件按 500 字符、80 字符重叠切分后的文本单元，是向量化的最小单位。 |
| **向量编号（vector_id）** | 分块在向量索引中的标识，格式 `file_{文件号}_chunk_{分块序号}`。 |
| **上下文（context）** | 向量检索片段与图谱推理结果拼接而成的一段文本，作为「参考知识」注入提示词。 |
| **AI 问诊会话（ConsultSession）** | 一名患者与 AI 的连续对话容器，含标题与消息计数。 |
| **人工问诊工单（DoctorConsult）** | 患者向真人医生提交的咨询请求，可指定医生，也可留空成为「待分配」工单。 |
| **待分配工单** | `doctor_id` 为空的工单：对所有医生可见，由首位回复的医生认领。 |
| **健康档案（HealthRecord）** | 医生为患者建立的就诊记录，含档案类型、诊断、治疗方案与处方。 |
| **角色（role）** | 取值为 `user`（患者）、`doctor`（医生）、`admin`（管理员）。系统无角色字段，角色由登录时提交并在令牌中传递。 |
| **当前用户（CurrentUser）** | 一次请求中被令牌解析出来的身份，携带用户号、用户名、角色与该角色对应的实体行。 |
| **统一响应外壳** | 所有接口共用的 `{code, message, data}` 结构。业务失败时 HTTP 状态可能仍为 200，需依据 `code` 判断。 |
| **SSE 帧** | 流式问答的传输单元，共四种类型：`session`、`content`、`done`、`error`。 |
| **图谱可视化** | 把图数据库节点与关系转为「节点 + 连线」结构供前端力导向图渲染，节点按标签分三类着色。 |
| **症状推理** | 由症状列表反查可能疾病并按覆盖率排序的功能，独立于 AI 问答链路，不调用大模型。 |

**术语表指出的一处命名歧义**：代码字段名 `probability`（在 `graph_service.py:84` 计算、前端作为「匹配度」展示）容易与统计学意义上的概率混淆，其真实含义是覆盖率。本表以「`probability` 字段」收录并在定义中澄清，建议后续在术语层面统一，但本规范不改变代码行为。

## 附录 B　现状事实与边界

本节只陈述代码当前行为及其直接后果，**不含改进建议、不含方案取舍**。

### B.1 鉴权覆盖现状

**无需登录即可访问的接口**（共 4 个），均与知识图谱有关：

| 接口 | 返回内容 |
|---|---|
| `GET /api/v1/graph/full` | 全部 693 个节点与 1 045 条关系，**无条数上限** |
| `GET /api/v1/graph/subgraph` | 任一实体的一跳邻居，上限 30 条关系 |
| `GET /api/v1/graph/search` | 按关键字搜索图谱实体，上限 20 条 |
| `GET /api/v1/graph/disease/{name}` | 任一疾病的完整详情（症状、药物、检查、并发症、饮食） |

**其他无需登录的接口**（属设计预期，非缺陷）：登录、注册；医生公开列表；科室公开列表；文章公开列表与详情；公告公开列表与详情；根路径。

**已知越权可表达路径**：

| 情形 | 位置 | 后果 |
|---|---|---|
| 读取他人会话消息 | `api/v1/chat.py:29` 仅按会话号过滤，不校验归属 | 任一患者可读取任意会话号对应的全部消息正文 |
| 回复任意工单 | `api/v1/consult.py:62` 按工单号查找，不校验归属 | 任一医生可回复未被指派的工单，或已被他人指派的工单，并成为其负责医生 |

### B.2 凭据与传输现状

| 事实 | 位置 |
|---|---|
| 口令以**明文**存储，比对为直接字符串相等 | `core/security.py:10-17`；写入点见 `user.py:70`、`doctor.py:95`、`auth_service.py:65`、`profile.py:78` |
| 令牌签名密钥**硬编码**在源码中 | `core/config.py:40` |
| 关系库口令、图数据库口令均为硬编码常量 | `core/config.py:15, 22` |
| 跨域策略为 `allow_origins=["*"]` 且 `allow_credentials=True` | `main.py:62-68` |
| 除大模型密钥外，无任何配置来自环境变量 | `core/config.py` 全文 |

### B.3 逻辑失效点

| 事实 | 位置 | 直接后果 |
|---|---|---|
| 22 条症状别名中，21 条在对话链路中不可达 | 提取表 `rag_service.py:96-101` 与别名表 `graph_service.py:11-34` 仅交集 `发烧` | 患者用口语说「头疼」「肚子痛」时，对话链路不会触发图谱推理 |
| 实体子图查询的深度参数无效，且存在一段从未执行的查询 | `graph_service.py:130` 的 `depth` 参数未被使用；`graph_service.py:135-144` 声明的两跳查询字符串从未传给执行接口，实际执行的是 `:149` 的单跳查询 | 名为「子图」的接口实际只返回一跳邻居 |
| 图谱结果进提示词时被截断为 5 条，但算出 10 条 | `rag_service.py:145-155` | 第 6–10 条结果仅回传前端，不参与回答生成 |
| 用户消息先落库、助手消息后落库 | `chat.py:54-56` 与 `chat.py:89-106` | 流中途失败时，会话中会留下无回复的用户消息，且消息计数不增加 |
| 传入他人会话号时静默新建会话 | `chat.py:42-51` | 前端不会收到错误，而是意外获得一个新会话 |
| 科室删除只校验医生不校验预约 | `department.py:117-119` | 科室可被删除而预约仍指向它，列表展示科室名为空 |
| 预约状态接口在记录不存在时仍返回成功 | `appointment.py:101-108` | 调用方无法区分「更新成功」与「记录不存在」 |
| 文章与公告的更新、删除不校验存在性 | `article.py:81, 95`；`notice.py:70, 87` | 恒返回「更新成功」「删除成功」 |
| 无状态迁移校验 | 所有 status 写入点 | 可将预约从「已完成」改回「待确认」，或写入未定义的状态值 |
| 建表脚本的目标文件不存在 | `scripts/import_sql.py:5` 指向 `server/sql/db_ai_medical.sql`，该文件与目录均不存在 | 该脚本按现状执行会读取失败 |

### B.4 数据完整性现状

| 事实 |
|---|
| 14 个实体**均未声明外键**，跨实体引用全部为普通整数编号 |
| 高频过滤字段（`user_id`、`doctor_id`、`department_id`、`status`、`visit_date`、`create_time`、`file_id`）**没有任何索引声明** |
| 唯一性约束仅存在于三张账号表的 `username`；**同一登录名可同时是患者、医生与管理员** |
| 所有级联删除均为应用层手工实现；未指派工单在医生被删除后仍然存在 |
| 知识库文件的上传人信息（编号 + 角色）在上传人被删除后不被清理 |
| 不存在「每个时段一个号」「一单一次回复」「一次就诊一份档案」之类的业务约束，也不存在评价/评分实体 |

### B.5 数据内容现状

| 事实 |
|---|
| 图数据库灌数内容含混合语言与首尾空格未清理的字符串，例如疾病节点 `慢性 daily 头痛`，症状节点 ` knee pain`，食物节点 ` cranberry juice`、` sticky 食物` |
| 同名节点存在于不同标签下：`失眠`、`贫血`、`骨折`、`高血压` 同时是疾病节点与症状节点；`维生素D` 同时是药物节点与食物节点 |
| `坚果` 与 `红肉` 同时出现在「宜吃」与「忌吃」关系中（分属不同疾病） |
| 84 个并发症节点只有名称，无科室、症状、药物等任何其他关联 |
| 图数据库灌数含 60 个主疾病，人工问诊与预约功能不依赖图谱内容 |

### B.6 覆盖范围说明

本文档覆盖 `server/` 全部 54 个源码文件与 `client/src/` 全部 39 个文件，共 73 个 HTTP 端点、14 个实体、6 类图谱节点、7 类图谱关系。未覆盖：`node_modules`、Python 虚拟环境、前端构建产物目录，以及关系库建表脚本（该文件不存在于本工程中）。
