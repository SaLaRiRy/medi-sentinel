"""本地重排（TICKET-AC-04）：只重排前 N 条、失败退回原序、默认关闭、懒加载。

全部用假重排器，**不加载 1.1 GB 的 ONNX 文件**，也不需要网络。
"""

from core.config import Settings
from rag.hybrid import RERANK_CANDIDATES, HybridRetriever
from rag.rerank import OnnxReranker


def hit(file_name: str, distance: float = 0.1) -> dict:
    return {
        "content": f"{file_name} 的正文",
        "metadata": {"file_name": file_name},
        "distance": distance,
    }


class FakeStore:
    def __init__(self, hits=()) -> None:
        self._hits = list(hits)

    async def search(self, query: str, top_k: int = 5):
        return self._hits[:top_k]

    async def all_documents(self):
        return []

    async def add_chunks(self, *, file_id: int, file_name: str, chunks) -> int:
        return len(chunks)

    async def delete_by_file_id(self, file_id: int) -> None:
        return None

    async def count_by_file_id(self, file_id: int) -> int:
        return 0


class RecordingReranker:
    """按给定分数重排；记录每次调用看到的 query 与文档。"""

    def __init__(self, scores=(), *, failing: bool = False) -> None:
        self._scores = list(scores)
        self._failing = failing
        self.calls: list[tuple[str, list[str]]] = []

    def score(self, query, documents):
        self.calls.append((query, list(documents)))
        if self._failing:
            raise RuntimeError("onnxruntime session failed")
        return self._scores[: len(documents)]


async def test_a_reranker_reorders_the_fused_head():
    store = FakeStore([hit("a.md"), hit("b.md"), hit("c.md")])
    reranker = RecordingReranker([0.1, 5.0, 1.0])
    retriever = HybridRetriever(store, reranker=reranker)

    result = await retriever.search("问句", top_k=3)

    assert [item["metadata"]["file_name"] for item in result] == ["b.md", "c.md", "a.md"]
    assert reranker.calls[0][0] == "问句"


async def test_only_the_first_n_candidates_are_reranked():
    store = FakeStore([hit(f"{index}.md") for index in range(1, 16)])
    reranker = RecordingReranker()
    retriever = HybridRetriever(store, reranker=reranker)

    result = await retriever.search("问句", top_k=5)

    assert len(reranker.calls) == 1
    assert len(reranker.calls[0][1]) == RERANK_CANDIDATES
    assert len(result) == 5


async def test_a_failing_reranker_keeps_the_fused_order():
    store = FakeStore([hit("a.md"), hit("b.md"), hit("c.md")])
    baseline = await HybridRetriever(store).search("问句", top_k=3)
    reranker = RecordingReranker(failing=True)

    result = await HybridRetriever(store, reranker=reranker).search("问句", top_k=3)

    assert [item["metadata"]["file_name"] for item in result] == [
        item["metadata"]["file_name"] for item in baseline
    ]


async def test_a_short_result_is_not_reranked():
    reranker = RecordingReranker([1.0])
    retriever = HybridRetriever(FakeStore([hit("only.md")]), reranker=reranker)

    await retriever.search("问句", top_k=5)

    assert reranker.calls == []


async def test_a_mismatched_score_count_is_ignored():
    """重排器返回的分数条数不对时要退回原序，不能按错位的名次重排。"""
    store = FakeStore([hit("a.md"), hit("b.md"), hit("c.md")])
    baseline = await HybridRetriever(store).search("问句", top_k=3)
    reranker = RecordingReranker([9.0])

    result = await HybridRetriever(store, reranker=reranker).search("问句", top_k=3)

    assert result == baseline


# --- 装配与懒加载 -------------------------------------------------------------


def test_rerank_is_off_by_default():
    settings = Settings(_env_file=None)

    assert settings.rerank_model_dir == ""


def test_build_vector_store_wires_the_reranker_only_when_configured():
    from adapters import build_vector_store

    off = build_vector_store(Settings(_env_file=None))
    on = build_vector_store(
        Settings(_env_file=None, rerank_model_dir=r"C:\models\bge-reranker-base")
    )

    assert off._reranker is None
    assert isinstance(on._reranker, OnnxReranker)


def test_the_onnx_reranker_loads_lazily():
    """构造一个指向不存在目录的重排器：构造本身不能碰磁盘。"""
    reranker = OnnxReranker(r"C:\definitely\missing\model")

    assert reranker._session is None
