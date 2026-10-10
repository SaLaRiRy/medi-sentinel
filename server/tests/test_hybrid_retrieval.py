"""混合检索（TICKET-AC-02）：分词、RRF 融合、两道门、写路径失效、端口形状。

全部用假 store，不碰 Chroma / 嵌入服务 / 网络。
"""

import pytest

from rag.hybrid import (
    MAX_VECTOR_DISTANCE,
    RETRIEVAL_MIN_SCORE,
    RRF_K,
    HybridRetriever,
    rrf_fuse,
    tokenize,
)
from rag.store import VectorStore
from skills.ports import RetrievalPort


def hit(file_name: str, content: str, distance: float = 0.1) -> dict:
    return {
        "content": content,
        "metadata": {"file_name": file_name},
        "distance": distance,
    }


class FakeStore:
    """向量支路的假替身：固定返回给定的命中，并记录调用与语料读取次数。"""

    def __init__(self, hits=(), documents=(), *, failing=False) -> None:
        self._hits = list(hits)
        self._documents = list(documents)
        self._failing = failing
        self.search_calls: list[tuple[str, int]] = []
        self.document_reads = 0

    async def search(self, query: str, top_k: int = 5):
        if self._failing:
            raise RuntimeError("chroma unavailable")
        self.search_calls.append((query, top_k))
        return self._hits[:top_k]

    async def all_documents(self):
        self.document_reads += 1
        return list(self._documents)

    async def add_chunks(self, *, file_id: int, file_name: str, chunks) -> int:
        return len(chunks)

    async def delete_by_file_id(self, file_id: int) -> None:
        return None

    async def count_by_file_id(self, file_id: int) -> int:
        return 0


# --- 分词 ---------------------------------------------------------------------


def test_tokenize_splits_chinese_into_character_bigrams():
    assert tokenize("高血压") == ["高血", "血压"]


def test_tokenize_keeps_ascii_words_and_digits_whole():
    assert tokenize("HbA1c 6.5 高血压") == ["hba1c", "6", "5", "高血", "血压"]


def test_tokenize_keeps_a_lone_chinese_character():
    assert tokenize("肾 高") == ["肾", "高"]


# --- RRF 融合 ----------------------------------------------------------------


def test_rrf_ranks_a_document_found_by_both_lists_first():
    a, b, c = hit("a.md", "A"), hit("b.md", "B"), hit("c.md", "C")

    fused = rrf_fuse([[a, b], [b, c]])

    assert [item["content"] for item, _ in fused] == ["B", "A", "C"]
    # 两路都命中的 B 分数是两路之和（k=60）。
    assert fused[0][1] == pytest.approx(1 / (RRF_K + 2) + 1 / (RRF_K + 1))


def test_rrf_is_stable_for_ties():
    first, second = hit("a.md", "A"), hit("b.md", "B")

    assert rrf_fuse([[first], [second]]) == rrf_fuse([[first], [second]])
    assert [item["content"] for item, _ in rrf_fuse([[first], [second]])] == ["A", "B"]


def test_rrf_keeps_the_vector_payload_for_a_document_found_by_both_lists():
    vector = hit("a.md", "A", distance=0.25)
    bm25 = hit("a.md", "A", distance=1.0)

    fused = rrf_fuse([[vector], [bm25]])

    assert fused[0][0]["distance"] == 0.25


# --- 两道门 -------------------------------------------------------------------


async def test_a_far_vector_hit_never_reaches_the_result():
    store = FakeStore(hits=[hit("far.md", "无关内容", distance=MAX_VECTOR_DISTANCE + 0.1)])
    retriever = HybridRetriever(store)

    assert await retriever.search("高血压吃什么药", top_k=5) == []


async def test_the_rrf_threshold_drops_hits_ranked_below_the_min_rank():
    # 向量路给 11 条（名次 1..11），BM25 路空：第 11 名只有 1/71 < 1/70 被丢弃。
    hits = [hit(f"{index}.md", f"分块{index}", distance=0.1) for index in range(1, 12)]
    retriever = HybridRetriever(FakeStore(hits=hits))

    result = await retriever.search("query", top_k=20)

    assert len(result) == 10
    assert result[-1]["content"] == "分块10"
    assert RETRIEVAL_MIN_SCORE == pytest.approx(1 / (RRF_K + 10))


async def test_bm25_brings_in_a_hit_the_vector_side_missed():
    vector = hit("向量.md", "与问句语义相近但字面无关", distance=0.2)
    documents = [{"content": "偏头痛发作前可有视觉先兆：闪光、暗点", "metadata": {"file_name": "偏头痛.md"}}]
    retriever = HybridRetriever(FakeStore(hits=[vector], documents=documents))

    result = await retriever.search("偏头痛的先兆", top_k=5)

    assert {item["metadata"]["file_name"] for item in result} == {"向量.md", "偏头痛.md"}


async def test_a_bm25_only_hit_carries_the_placeholder_distance():
    documents = [{"content": "痛风急性发作常用非甾体抗炎药", "metadata": {"file_name": "痛风.md"}}]
    retriever = HybridRetriever(FakeStore(hits=[], documents=documents))

    result = await retriever.search("痛风用什么药", top_k=5)

    assert result[0]["metadata"]["file_name"] == "痛风.md"
    assert result[0]["distance"] == 1.0


# --- 降级与写路径 -------------------------------------------------------------


async def test_an_unavailable_vector_branch_still_raises():
    """向量支路不可用要如实抛出，由 Skill 记 `degraded`（SPEC.md 3.6）。"""
    retriever = HybridRetriever(FakeStore(failing=True))

    with pytest.raises(RuntimeError):
        await retriever.search("query")


async def test_adding_chunks_invalidates_the_bm25_index():
    store = FakeStore(documents=[])
    retriever = HybridRetriever(store)
    await retriever.search("第一次", top_k=5)
    await retriever.search("第二次", top_k=5)
    assert store.document_reads == 1

    await retriever.add_chunks(file_id=1, file_name="新.md", chunks=["新分块"])
    await retriever.search("第三次", top_k=5)

    assert store.document_reads == 2


async def test_the_retriever_is_both_ports():
    retriever = HybridRetriever(FakeStore())

    assert isinstance(retriever, VectorStore)
    assert isinstance(retriever, RetrievalPort)
