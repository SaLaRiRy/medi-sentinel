# 04: 本地 ONNX 重排（BAAI/bge-reranker-base）

**What to build:** 在检索之后、编排之前插入**本地交叉编码器重排**，把票 03 的
`recall@1` / `MRR` 抬上去（目标：相关文档排到 top-1）。方案已在本机实测跑通，照做即可：

| 项 | 实测值 |
|---|---|
| 模型目录 | `C:\Users\87590\models\models\BAAI--bge-reranker-base\snapshots\master` |
| ONNX 文件 | `onnx/model.onnx`，**1112.5 MB，自带权重、单文件** |
| 加载耗时 | **2504 ms**（一次性） |
| 推理耗时 | **单对 29.8 ms / 3 对 52.9 ms**（CPU） |
| 输入 | 只要 `input_ids` + `attention_mask`（**连 `token_type_ids` 都不需要**） |
| 输出 | `logits`，形状 `[batch, 1]` |
| 排序验证 | query「高血压吃什么药」→ 相关 5.929 / 无关 -10.1968 / -7.306 ✅ |
| 运行时 | `onnxruntime 1.30.0` + `tokenizers`（**已在 `.venv`**） |

**不要引入 torch / sentence-transformers**：venv 里没有；系统 Python
（`C:\Program Files\Python313\python.exe`）的 `torch 2.14.1+cpu` 那条路**不需要走**。
**`onnxruntime` 与 `tokenizers` 都不在 `server/requirements.txt`（14 行）里，必须显式补登。**

**Blocked by:** 02（要有融合后的候选集）、03（要有可量的指标）

**Status:** done
Completed: f7912ff

## 关键设计约束：必须做成「可回放」，但不一定新增端口

ONNX 只允许出现在**录制时的真实适配器**里。两种落法，票内先做 A，除非有硬理由才升 B：

- **A（首选）**：重排放在 `RetrievalPort` **实现层内部**（`rag/hybrid.py` 内调用
  `rag/rerank.py`）。端口签名不变 → `server/regression/ports.py` 零改动、
  `tests/doubles.py` 零改动、`baseline.ports` 键不变（spec.md 4.4）。
- **B（若必须暴露为独立能力）**：新增 `RerankPort` → 必须**同时**进：录制侧、回放侧、
  `BaselineCase.ports` 键、`tests/doubles.py` 替身，并重录 baseline。
  且 `server/regression/ports.py` **不得 import onnxruntime/onnx**
  （docstring 承诺 + AST 测试 `server/tests/test_regression_record_replay.py:169-179`）。

## 验收清单

- [ ] 重排后相关文档排到 top-1（票 03 的标注集上 `MRR` 与 `recall@1` 均不下降）
- [x] ~~P95 增量 < 100 ms~~ → **按实测改判**：真实分块接近 512 token，单对约 150 ms，
      100 ms 的预算对这个模型在 CPU 上不可达。改判为「**默认关闭**，打开后以实测表交代
      代价与收益」——见 Comments 的配置扫描表。用户的授权是「遇到选择选推荐值」，
      我的推荐是**默认关闭 + 文档化取舍**，而不是把 +1.2 s 藏进默认路径。
- [ ] 回放零外部依赖：`pytest server/tests/test_regression_record_replay.py` 全绿，
      回放路径**不 import** `onnxruntime` / `onnx`
- [ ] 模型缺失 / 加载失败 → **降级为原序**，不产生 503/504（检索是增强支路，`SPEC.md:398`）
- [ ] **默认关闭**：`Settings.rerank_model_dir: str = ""`（空 = 不重排），
      与 `fallback_llm_model` 同风格；路径不写死在代码里
- [ ] `onnxruntime` / `tokenizers` 补进 `requirements.txt`
- [ ] divergence 登记：`S-2` / scope **`stack`**（框架级检索变更；**不**进豁免集）
- [ ] `vector_retrieval/SKILL.md` 边界情况补「重排不可用时保持原序」

## TDD 要点

- 重排器用**假模型**（注入打分函数）测排序语义，**不加载 1.1 GB 文件**。
- 加载失败 → 返回原序（异常注入）。
- 默认关闭：`rerank_model_dir=""` 时 `search` 结果与票 02 逐位相等。
- 真模型的单次实测（加载耗时、单对耗时、三条验证分数）单独跑一次贴 Comments，不进套件。

## 边界与坑

- `tokenizers` 的 `enable_truncation(max_length=512)` 与 `enable_padding(pad_id=0,
  pad_token="[PAD]")` 都要显式设置，否则 batch 推理会因长度不齐报错
  （探针 `_probe_rerank.py` 已验证的写法）。
- 模型在仓库之外（用户目录），**不能进 git**；`.env` 里配置，`.env.example` 只列变量名与空值。

## Comments

**完成（2026-10-11）。** 本地 ONNX 交叉编码器重排接进检索端口，**默认关闭**。

### 交付

| 文件 | 变更 |
|---|---|
| `server/rag/rerank.py`（新增） | `Reranker` 协议 + `OnnxReranker`（懒加载、批量前向、`onnxruntime`/`tokenizers` 只在这里按需导入） |
| `server/rag/hybrid.py` | `_rerank`：只重排融合后的前 `RERANK_CANDIDATES` 条，跑在 `asyncio.to_thread` 里；缺失或抛错一律退回原序 |
| `server/core/config.py` | `rerank_model_dir: str = ""`（空 = 不重排） |
| `server/adapters.py` | `build_vector_store` 按配置装配重排器 |
| `server/.env.example` | `RERANK_MODEL_DIR`（含目录结构说明） |
| `server/requirements.txt` | `numpy` / `onnxruntime` / `tokenizers`（前两者此前靠传递依赖存在，本票显式登记） |
| `.scratch/medisentinel/intentional-divergences.md` | `S-2` / `stack` |
| `vector_retrieval/SKILL.md` | 边界情况补「重排不可用时保持原序」 |

### 验收改判：100 ms 那条线不成立

票面写的是「P95 增量 < 100 ms（3–5 对重排 ≈ 53 ms 实测）」。那 53 ms 来自**探针的短句**
（`_probe_rerank.py` 用的是 30 字左右的样本）。真实分块是 500 字 ≈ 512 token，
单对成本约 150 ms。我在 retrieval-v1 的 30 条上做了配置扫描（CPU，去掉首次加载）：

| 配置 | recall@1 | recall@5 | MRR | 单次检索中位 | 增量 |
|---|---|---|---|---|---|
| **不重排** | 0.9833 | 0.9833 | 1.0000 | 204.9 ms | — |
| N=8 / maxlen=512 | 0.9833 | **1.0000** | 1.0000 | 1442.1 ms | **+1237 ms** |
| N=8 / maxlen=256 | 0.9500 | 1.0000 | 0.9833 | 979.1 ms | +774 ms |
| N=5 / maxlen=256 | 0.9833 | 0.9833 | 1.0000 | 692.3 ms | +487 ms |
| N=3 / maxlen=256 | 0.9833 | 0.9833 | 1.0000 | 489.6 ms | +285 ms |
| N=3 / maxlen=128 | 0.9167 | 0.9833 | 0.9667 | 348.3 ms | +143 ms |

两个可读的结论：

1. **只有 N=8 / 512 能拿到收益**：recall@5 从 0.9833 → **1.0000**
   （q13「过敏性鼻炎和感冒有什么区别」的第二篇文档被拉回 top-5）。任何降配都把这 1.7pp 吃回去。
2. **MRR 无提升空间**：不重排时 MRR 已经是 1.0（票 02 的 RRF 融合已经把首条命中的文档排在第 1 位），
   所以「重排把相关文档排到 top-1」这条验收在数值上只能"保持不下降"。

→ **决策（用户授权「选推荐值」）**：实现保留、**默认关闭**，`RERANK_CANDIDATES = 8` / `max_length = 512`
作为实测最优配置写进常量注释。理由：把「+1.7pp recall@5」换「每次问诊多 1.2 秒」当默认值
不划算，而"能开、能量化、能说清取舍"本身就是这次改造要的东西。要开就在 `.env` 里填
`RERANK_MODEL_DIR`。

### TDD

`server/tests/test_rerank.py` 8 项：重排生效 1 / 只重排前 N 条 1 / 失败退回原序 1 /
结果太短不调用 1 / 分数条数不匹配退回原序 1 / 默认关闭 1 / 装配分支 1 / 懒加载 1。
全部用假重排器，**不加载 1.1 GB 模型**，不需要网络。

### 套件

- 后端 `pytest -q --basetemp=.tmp\pytest-user` → **891 passed**（883 + 8 新增）
- 前端未改动

### divergence

`S-2`（scope `stack`）已登记。
