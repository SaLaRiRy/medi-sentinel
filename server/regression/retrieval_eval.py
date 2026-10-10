"""检索质量评测（TICKET-AC-03）：recall@k 与 MRR。

**标注集先定稿再跑指标**（用户 2026-10-11 拍板）：cases/retrieval-v1.json 的真值
一经确认即冻结，**不允许事后回溯调整**——否则指标只是把真值往结果上凑。要改口径
只能出新版本 retrieval-v2.json。

**标注口径**：二值相关——命中的文件名出现在该用例的 relevant 里即算相关；
一个问句可以标注多篇（例如「过敏性鼻炎和感冒的区别」同时标两篇）。
不区分相关度强弱，因此这里**不报 nDCG**。

纯函数（recall_at / reciprocal_rank）与端口调用分开：前者可在无任何外部依赖下
单测，后者才需要真实 RetrievalPort。
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel, Field

from regression.schema import default_store
from skills.ports import RetrievalPort

# 报几个 k。RETRIEVAL_TOP_K = 5，所以 1 与 5 是唯一有意义的两个点。
REPORTED_K = (1, 5)


class RetrievalCase(BaseModel):
    """一条标注：一个问句 + 一个相关文件列表（二值相关）。"""

    id: str
    query: str = Field(min_length=1)
    relevant: list[str] = Field(min_length=1)


class RetrievalCaseSet(BaseModel):
    version: str
    frozen_at: str
    note: str = ""
    cases: list[RetrievalCase]


class RetrievalReport(BaseModel):
    """一次检索评测的结果。三项指标都按用例取平均。"""

    case_set_version: str
    case_count: int
    recall_at_1: float
    recall_at_5: float
    mrr: float
    top_k: int


def recall_at(retrieved: Sequence[str], relevant: Sequence[str], k: int) -> float:
    """recall@k = 前 k 条里命中的相关文档数 ÷ 相关文档总数（单条用例的值）。"""
    expected = set(relevant)
    if not expected:
        return 0.0
    return len(set(retrieved[:k]) & expected) / len(expected)


def reciprocal_rank(retrieved: Sequence[str], relevant: Sequence[str]) -> float:
    """第一个相关文档的排名倒数；一个都没有则为 0。"""
    expected = set(relevant)
    for position, name in enumerate(retrieved, start=1):
        if name in expected:
            return 1.0 / position
    return 0.0


def file_names_of(hits: Sequence[Mapping[str, object]]) -> list[str]:
    """把命中序列投影成文件名序列（顺序即排名）。"""
    return [str((hit.get("metadata") or {}).get("file_name", "")) for hit in hits]


async def evaluate_retrieval(
    retriever: RetrievalPort,
    case_set: RetrievalCaseSet,
    *,
    top_k: int = 5,
) -> RetrievalReport:
    """跑一遍标注集，按用例取平均。端口异常照常抛出（评测不该吞掉降级）。"""
    recalls_one: list[float] = []
    recalls_five: list[float] = []
    ranks: list[float] = []
    for case in case_set.cases:
        names = file_names_of(await retriever.search(case.query, top_k=top_k))
        recalls_one.append(recall_at(names, case.relevant, 1))
        recalls_five.append(recall_at(names, case.relevant, top_k))
        ranks.append(reciprocal_rank(names, case.relevant))
    total = len(case_set.cases) or 1
    return RetrievalReport(
        case_set_version=case_set.version,
        case_count=len(case_set.cases),
        recall_at_1=sum(recalls_one) / total,
        recall_at_5=sum(recalls_five) / total,
        mrr=sum(ranks) / total,
        top_k=top_k,
    )


def case_set_path(version: str, *, cases_dir: Path | None = None) -> Path:
    base = cases_dir if cases_dir is not None else default_store().cases_dir
    return Path(base) / f"{version}.json"


def load_case_set(version: str, *, cases_dir: Path | None = None) -> RetrievalCaseSet:
    path = case_set_path(version, cases_dir=cases_dir)
    return RetrievalCaseSet.model_validate(
        json.loads(path.read_text(encoding="utf-8"))
    )


__all__ = [
    "REPORTED_K",
    "RetrievalCase",
    "RetrievalCaseSet",
    "RetrievalReport",
    "case_set_path",
    "evaluate_retrieval",
    "file_names_of",
    "load_case_set",
    "recall_at",
    "reciprocal_rank",
]
