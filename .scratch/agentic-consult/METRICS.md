# METRICS —— 项目指标的唯一权威清单（引用前必读）

**建档**：2026-10-11 · **性质**：项目侧**收口页**，决定简历与面试能怎么引用。

**为什么需要这一页**：本项目的结论是**增量**写进票 10 / 票 11 / 票 12 / `spec.md` §8.x /
`map.md` 的，同一个数字被修正过好几次（比率形态 → 覆盖率形态；0.0582 → 0.0663；
189 → 196）。散在各处必然自相矛盾，所以**对外引用只准用本页**；
票内那些标注着"修复前 / 历史记录"的段落**只能当过程留痕，不能当结论**。

**读法**：每行给「值 / 口径（分母是什么、样本多少、何时录的）/ 出处文件:行」。

---

## 一、✅ 可引用

| # | 值 | 口径 | 出处 |
|---|---|---|---|
| 1 | 知识库 **17 篇 / 42 chunk**，`vector_status` 全为 2 | 活库 MySQL 实计数，2026-10-11 | `server/docs_seed/`（17 个文件）；`issues/01-expand-knowledge-base.md:76` |
| 2 | `recall@5` = **0.9833**（默认路径，不重排）/ **1.0000**（开重排 N=8/512） | 30 条人工标注 query-文档对（`retrieval-v1`，2026-10-11 定稿冻结），跑**真实** `RetrievalPort` + 活库嵌入 | `issues/03-retrieval-quality-eval.md:78`（默认路径原始输出）；`issues/04-onnx-rerank.md:93-94`（两行对照） |
| 3 | `recall@1` = **0.9833**、`MRR` = **1.0000** | 同上（默认路径） | 同上 |
| 4 | 离题问句（"今天天气怎么样""股票怎么开户"）**返回空结果** | 阈值 `MAX_VECTOR_DISTANCE = 0.60`，按活库余弦距离标定（相关最佳 0.25–0.34、离题最低 0.699） | `server/rag/hybrid.py:51`；`issues/02-hybrid-retrieval-rrf.md:129,131` |
| 5 | 红旗拦截率 **1.0** / 误拦率 **0.0** | v3 活库基线：**6 条红旗用例真实跑、真实拦截**（不是替身自证） | `issues/10-live-baseline-recording.md:279` |
| 6 | 断言总数 **1267** / 可判定 **400（32%）** / 未判定 **867（68%）** | v3 活库基线 20 条真实回答；`_assertions` 切出的**全部非空断言** | `server/regression/calibers.py:10-14`；`issues/12-assertion-extraction-calibers.md:45-48` |
| 7 | **33 条**被字面层标记无据，其中 **19 条由行首列表编号触发**（排除编号后 33 → 14） | 同上。「**24 条**」是另一个量——"token **全部是数字**"的条数（含 `15–20 分钟` 这类临床数值），**不要与 19 混用** | `issues/12-assertion-extraction-calibers.md:45-48`；`scripts/regression.py hallucination-calibers` |
| 8 | 对外只报一个数字时：`literal_marked_ratio` = 33 ÷ 1267 = **0.0260** | 分母**固定为全部非空断言**，口径之间直接可比（②③ 为 0.0110 / 0.0103）。**必须标注"字面标记率，不是幻觉率"** | `server/regression/calibers.py`；`spec.md` §8.5 |

**复现命令**（都在 `server/` 下运行，`.env` 是相对路径，故必须在该目录）：

```
.venv/Scripts/python.exe scripts/regression.py hallucination-calibers --baseline-version v3
.venv/Scripts/python.exe scripts/regression.py retrieval-eval --set retrieval-v1   # 需要联网
.venv/Scripts/python.exe scripts/regression.py replay --case-set v3 --baseline-version v3
```

---

## 二、❌ 不可引用（逐条写明原因）

| 值 | 为什么不能引用 | 出处 |
|---|---|---|
| `diagnosis_drift_rate` = 0.0 | **回放路径上是恒真式**：`baseline_candidates` 与回放候选都取自同一份基线，必然相等 → **代码改坏也报 0**。实测 v1 与 v3 的候选在 **12/20** 条上明显不同，两边仍报 0.0 | `server/regression/replay.py:174`；`server/regression/metrics.py:247` |
| `latency` 的 v1→v3 差值 | 回放**不测量延迟**——取的是基线录制值（`duration_ms=case.duration_ms`）。那是"两种录制产物之差"，不是优化前后。v3 的 60 s 只能表述为「**v3 录制的**单次生成耗时 P95 ≈ 60 s（真实模型、600 chunk）」 | `server/regression/replay.py:205` |
| `evidence_match_rate` = 1.0（v3） | 同一份快照**自我回放**的一致性自检，构造使然。它的正用途是**代码变更后重放旧基线**（v2 相对 v1 就是这么用的） | `issues/10-live-baseline-recording.md`；`spec.md` §8.5 |
| 任何 ratio 形态的"幻觉率"（0.0825 / 0.0664 / 0.0663） | 字面层**覆盖率仅 32%**，未评估的 867 条里大量是就医 / 急诊 / 警惕类安全提示；分子还含格式伪影。三个口径的分母不同（400 / 211 / 196），**横向不可比** | `issues/12-assertion-extraction-calibers.md`；`spec.md` §3.8 |
| 重排"提升检索质量"这类笼统说法 | 重排对 `recall@1` 与 `MRR` **零提升**（RRF 融合已把首条命中文档排在第 1 位），只把多标签用例 q13 的第二篇拉回 top-5（recall@5 +1/30），代价 **+1.24 s/次**，故默认关闭 | `issues/04-onnx-rerank.md:93-94` |

---

## 三、口径速记

- **分母**：检索指标的分母是 **30 条标注 query**；字面层有两套分母——
  `evaluable`（400，含可判定 token）与**全部非空断言**（1267）。**对外只用后者**。
- **样本与时间**：所有数字都是 **2026-10-11** 的活库 / 标注集快照。
  v3 基线是**不可复现的真实调用快照**（模型每次回答不同），但**回放逐字稳定**。
- **两条红线**：换**上下文**不得改变分母（AC-11）；换**口径**只改 `evaluable`（AC-12）。
- **本页未收录**：任何"覆盖率 / 比率"以外的拟合口径（如 nDCG）——标注集是二值相关，不适用。

## 变更记录

- 2026-10-11：建档为项目侧收口页。收敛此前散在票 10/11/12 与 `spec.md` §8.x 的增量结论：
  比率形态 → 覆盖率形态；0.0582 → **0.0663**；③ 的可判定条数 189 → **196**
  （单位窗口从 4 字符放宽到 6）；并明确 **24（token 全为数字）≠ 19（由行首编号触发）**。
