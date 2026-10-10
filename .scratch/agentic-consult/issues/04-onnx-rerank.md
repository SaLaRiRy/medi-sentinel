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

**Status:** ready-for-agent

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
- [ ] P95 增量 < 100 ms（3–5 对重排 ≈ 53 ms 实测，留余量；记录测量方法）
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
