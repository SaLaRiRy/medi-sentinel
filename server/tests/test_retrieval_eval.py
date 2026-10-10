"""检索质量评测（TICKET-AC-03）：recall@k / MRR 与冻结的标注集。

纯函数用假检索端口断言，不碰 Chroma、嵌入与网络；另有一组标注集完整性检查，
保证真值是"先定稿"的：条数在区间内、id 唯一、每个 relevant 都是真实存在的种子文档。
"""

from pathlib import Path

import pytest

from regression.retrieval_eval import (
    RetrievalCase,
    RetrievalCaseSet,
    evaluate_retrieval,
    load_case_set,
    recall_at,
    reciprocal_rank,
)

SERVER_ROOT = Path(__file__).resolve().parents[1]
DOCS_SEED = SERVER_ROOT / "docs_seed"


def hit(file_name: str) -> dict:
    return {
        "content": f"{file_name} 的正文",
        "metadata": {"file_name": file_name},
        "distance": 0.2,
    }


class FakeRetriever:
    def __init__(self, mapping: dict[str, list[str]]) -> None:
        self._mapping = mapping
        self.calls: list[tuple[str, int]] = []

    async def search(self, query: str, top_k: int = 5):
        self.calls.append((query, top_k))
        return [hit(name) for name in self._mapping.get(query, [])][:top_k]


# --- 纯函数 -------------------------------------------------------------------


def test_recall_at_counts_only_the_top_k_window():
    assert recall_at(["b.md", "a.md"], ["a.md"], 1) == 0.0
    assert recall_at(["b.md", "a.md"], ["a.md"], 5) == 1.0


def test_recall_at_averages_over_the_labelled_documents():
    assert recall_at(["c.md", "b.md"], ["b.md", "c.md"], 5) == 1.0
    assert recall_at(["c.md"], ["b.md", "c.md"], 5) == 0.5


def test_recall_at_an_empty_label_is_zero():
    assert recall_at(["a.md"], [], 5) == 0.0


def test_reciprocal_rank_uses_the_first_relevant_position():
    assert reciprocal_rank(["b.md", "a.md"], ["a.md"]) == 0.5
    assert reciprocal_rank(["a.md"], ["a.md"]) == 1.0
    assert reciprocal_rank(["b.md"], ["a.md"]) == 0.0


# --- 端口评测 -----------------------------------------------------------------


_CASE_SET = RetrievalCaseSet(
    version="unit",
    frozen_at="2026-10-11",
    cases=[
        RetrievalCase(id="c1", query="问句一", relevant=["a.md"]),
        RetrievalCase(id="c2", query="问句二", relevant=["b.md", "c.md"]),
    ],
)


async def test_evaluate_retrieval_averages_the_three_metrics():
    retriever = FakeRetriever(
        {"问句一": ["b.md", "a.md"], "问句二": ["c.md", "b.md"]}
    )

    report = await evaluate_retrieval(retriever, _CASE_SET, top_k=5)

    assert report.case_count == 2
    assert report.recall_at_1 == pytest.approx((0.0 + 0.5) / 2)
    assert report.recall_at_5 == pytest.approx(1.0)
    assert report.mrr == pytest.approx((0.5 + 1.0) / 2)
    assert report.case_set_version == "unit"
    assert retriever.calls == [("问句一", 5), ("问句二", 5)]


async def test_evaluate_retrieval_counts_a_miss_as_zero():
    retriever = FakeRetriever({"问句一": ["z.md"], "问句二": ["z.md"]})

    report = await evaluate_retrieval(retriever, _CASE_SET, top_k=5)

    assert report.recall_at_5 == 0.0
    assert report.mrr == 0.0


async def test_evaluate_retrieval_is_reproducible():
    retriever = FakeRetriever({"问句一": ["a.md"], "问句二": ["b.md", "c.md"]})

    first = await evaluate_retrieval(retriever, _CASE_SET, top_k=5)
    second = await evaluate_retrieval(retriever, _CASE_SET, top_k=5)

    assert first.model_dump() == second.model_dump()


# --- 冻结的标注集 -------------------------------------------------------------


def test_retrieval_v1_is_frozen_and_within_the_agreed_size():
    case_set = load_case_set("retrieval-v1")

    assert case_set.version == "retrieval-v1"
    assert case_set.frozen_at
    assert 20 <= len(case_set.cases) <= 30
    assert len({case.id for case in case_set.cases}) == len(case_set.cases)


def test_every_label_points_at_a_real_seed_document():
    case_set = load_case_set("retrieval-v1")
    seeded = {path.name for path in DOCS_SEED.glob("*.md")}

    for case in case_set.cases:
        assert set(case.relevant) <= seeded, case.id


def test_a_case_needs_at_least_one_relevant_document():
    with pytest.raises(Exception):
        RetrievalCase(id="bad", query="问题", relevant=[])
