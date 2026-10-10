"""混合检索：向量 + BM25，RRF 融合，再按阈值过滤（TICKET-AC-02）。

**为什么融合**：向量检索擅长「换个说法问同一件事」，BM25 擅长精确词面命中
（药名、检查名、疾病名、缩写）。两条路的分数不可比（余弦距离 vs BM25 分数），
所以融合只看**排名**：RRF（Reciprocal Rank Fusion），
`score(d) = Σ_路 1 / (k + rank_路(d))`，取原论文的 `k = 60`。

**为什么写在端口内部**：编排层只调一次 `RetrievalPort.search`
（`skills/vector_retrieval/skill.py::run`）。融合放在实现层里，端口签名与调用序列
都不变——回归回放是纯 FIFO 游标（`regression/ports.py`），调用次数一变，
baseline 与回放会整体错位。

**两道门**：

1. `MAX_VECTOR_DISTANCE`：余弦距离超过它的**向量**命中不进入融合
   （该命中仍可由 BM25 路带进来）；
2. `RETRIEVAL_MIN_SCORE`：RRF 分低于它的命中丢弃——等价于「至少要在某一路里
   排进前 `RRF_MIN_RANK` 名」。候选深度 `CANDIDATE_K` 比输出 `top_k` 深，
   阈值才有意义（否则每个命中都必然在名次内，阈值恒为惰性）。

**降级**：向量支路不可用时 `search` 照常抛出，由 `vector-retrieval` Skill 记
`degraded`（SPEC.md 3.6）。本模块不吞异常，也不把 BM25 单路当作替代品。
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from rank_bm25 import BM25Okapi

from rag.store import VectorStore

RRF_K = 60

#: 两路各取前 `CANDIDATE_K` 名再融合，输出仍截到调用方给的 `top_k`。
CANDIDATE_K = 20

#: 一个命中至少要在某一路里排进前 `RRF_MIN_RANK` 名才保留。
RRF_MIN_RANK = 10
RETRIEVAL_MIN_SCORE = 1.0 / (RRF_K + RRF_MIN_RANK)

#: 余弦距离上限。初值 0.60，由票 03 的标注集校准后回写实测值。
MAX_VECTOR_DISTANCE = 0.6

#: BM25 单路命中没有embedding证据，用余弦距离的「无关」水平占位（同向为 0、
#: 正交为 1）；它只进 Skill 输出与 trace，不进 wire 契约。
_BM25_ONLY_DISTANCE = 1.0

_RUN = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]+")


def tokenize(text: str) -> list[str]:
    """中英混排的 BM25 切分：ASCII 词整词，连续汉字切成字符二元组。

    中文没有空格，按空白切等于整句一个 token，BM25 的 tf/idf 全部失效；
    字符二元组是中文检索里常用的轻量替代：不需要分词词典，确定性可测。
    """
    tokens: list[str] = []
    for match in _RUN.finditer(text.lower()):
        run = match.group(0)
        if run.isascii():
            tokens.append(run)
        elif len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[index : index + 2] for index in range(len(run) - 1))
    return tokens


def _key_of(hit: Mapping[str, Any]) -> tuple[str, str]:
    metadata = hit.get("metadata") or {}
    return str(metadata.get("file_name", "")), str(hit.get("content", ""))


def rrf_fuse(
    rankings: Sequence[Sequence[Mapping[str, Any]]], *, k: int = RRF_K
) -> list[tuple[Mapping[str, Any], float]]:
    """把多路排名融合成 `[(hit, score)]`，按分数降序、同分按 key 稳定排序。

    `rankings[0]` 的载荷优先保留：向量路带真实余弦距离，BM25 路没有。
    同一分块在两路都出现时只算一条，分数相加。
    """
    scores: dict[tuple[str, str], float] = {}
    payload: dict[tuple[str, str], Mapping[str, Any]] = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking, start=1):
            key = _key_of(hit)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            payload.setdefault(key, hit)
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return [(payload[key], score) for key, score in ordered]


class HybridRetriever:
    """`RetrievalPort` + `VectorStore`：双路检索，融合与阈值都在这一层内。

    写路径（`add_chunks` / `delete_by_file_id`）原样委托给内层 store，并在语料
    变化时让 BM25 索引失效——索引是进程内缓存，不失效就会检索到陈旧语料。
    """

    def __init__(
        self,
        store: VectorStore,
        *,
        candidate_k: int = CANDIDATE_K,
        min_score: float = RETRIEVAL_MIN_SCORE,
        max_distance: float = MAX_VECTOR_DISTANCE,
    ) -> None:
        self._store = store
        self._candidate_k = max(1, candidate_k)
        self._min_score = min_score
        self._max_distance = max_distance
        self._index: (
            tuple[list[Mapping[str, Any]], list[set[str]], BM25Okapi | None] | None
        ) = None

    # --- VectorStore：写路径原样委托，只多一件事 -----------------------------

    async def add_chunks(
        self, *, file_id: int, file_name: str, chunks: Sequence[str]
    ) -> int:
        stored = await self._store.add_chunks(
            file_id=file_id, file_name=file_name, chunks=chunks
        )
        self.invalidate()
        return stored

    async def delete_by_file_id(self, file_id: int) -> None:
        await self._store.delete_by_file_id(file_id)
        self.invalidate()

    async def count_by_file_id(self, file_id: int) -> int:
        return await self._store.count_by_file_id(file_id)

    def invalidate(self) -> None:
        """语料变了：下一次检索重建 BM25 索引。"""
        self._index = None

    async def close(self) -> None:
        close = getattr(self._store, "close", None)
        if callable(close):
            await close()

    # --- RetrievalPort ------------------------------------------------------

    async def search(
        self, query: str, top_k: int = 5
    ) -> Sequence[Mapping[str, Any]]:
        depth = max(self._candidate_k, top_k)
        vector_hits = [
            hit
            for hit in await self._store.search(query, depth)
            if float(hit.get("distance", 0.0)) <= self._max_distance
        ]
        fused = rrf_fuse([vector_hits, await self._bm25_rank(query, depth)])
        return [hit for hit, score in fused if score >= self._min_score][:top_k]

    async def _corpus(
        self,
    ) -> tuple[list[Mapping[str, Any]], list[set[str]], BM25Okapi | None]:
        if self._index is None:
            documents = list(await self._documents())
            tokenized = [
                set(tokenize(str(document.get("content", ""))))
                for document in documents
            ]
            index = (
                BM25Okapi([sorted(tokens) for tokens in tokenized]) if tokenized else None
            )
            self._index = (documents, tokenized, index)
        return self._index

    async def _documents(self) -> Sequence[Mapping[str, Any]]:
        documents = getattr(self._store, "all_documents", None)
        if documents is None:
            return []
        return await documents()

    async def _bm25_rank(
        self, query: str, depth: int
    ) -> list[Mapping[str, Any]]:
        documents, tokenized, index = await self._corpus()
        query_tokens = set(tokenize(query))
        if index is None or not query_tokens:
            return []
        scores = index.get_scores(sorted(query_tokens))
        # 「与问句有词面重叠」才是 BM25 命中。不用「分数 > 0」当门：语料很小时
        # BM25 的 IDF 可能整体为负，那样会把整个库滤空（本票实测踩到过）。
        candidates = [
            position
            for position, tokens in enumerate(tokenized)
            if query_tokens & tokens
        ]
        candidates.sort(key=lambda position: (-scores[position], position))
        return [
            {
                "content": documents[position].get("content", ""),
                "metadata": dict(documents[position].get("metadata") or {}),
                "distance": _BM25_ONLY_DISTANCE,
            }
            for position in candidates[:depth]
        ]
