"""Chroma 向量索引适配器（TICKET-013）。

以本地持久化模式运行（`FUNCTIONAL_SPEC.md` 6.2：目录 `server/chroma_db`、集合
`medical_knowledge`、余弦度量），并实现 B-3 的 `RetrievalPort` 与灌数用的
`VectorStore`。查询向量与分块向量的嵌入发生在端口之内，**不算**大模型生成调用
（`SPEC.md` 3.4）。

两个外部依赖都按需导入：`chromadb` 只在首次使用集合时导入，嵌入走异步 HTTP。
Chroma 客户端的调用是同步 SQLite，统一用 `asyncio.to_thread` 下放，避免阻塞
事件循环（`SPEC.md` 3.1 / 6.1 AC-B-24）。
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any, Mapping

import httpx

from models.knowledge import vector_id_of


class OpenAiCompatibleEmbedder:
    """兼容 OpenAI 接口的异步嵌入客户端（`FUNCTIONAL_SPEC.md` 6.2）。"""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        dimensions: int,
        batch_size: int = 10,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = base_url.rstrip("/") + "/embeddings"
        self._api_key = api_key
        self._model = model
        self._dimensions = dimensions
        self._batch_size = max(1, batch_size)
        self._client = client

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = list(texts[start : start + self._batch_size])
            response = await self.client.post(
                self._url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "input": batch,
                    "dimensions": self._dimensions,
                },
            )
            response.raise_for_status()
            data = sorted(response.json()["data"], key=lambda item: item["index"])
            vectors.extend(item["embedding"] for item in data)
        return vectors

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()


class ChromaVectorStore:
    """本地持久化 Chroma 之上的 `VectorStore` / `RetrievalPort`。"""

    def __init__(
        self,
        *,
        persist_dir: str,
        collection_name: str,
        embedder: OpenAiCompatibleEmbedder,
    ) -> None:
        self._persist_dir = persist_dir
        self._collection_name = collection_name
        self._embedder = embedder
        self._collection_cache: Any | None = None

    def _collection(self) -> Any:
        if self._collection_cache is None:
            import chromadb

            client = chromadb.PersistentClient(path=self._persist_dir)
            self._collection_cache = client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection_cache

    async def add_chunks(
        self, *, file_id: int, file_name: str, chunks: Sequence[str]
    ) -> int:
        documents = list(chunks)
        if not documents:
            return 0
        embeddings = await self._embedder.embed(documents)
        ids = [vector_id_of(file_id, index) for index in range(len(documents))]
        metadatas = [
            {"file_id": file_id, "file_name": file_name} for _ in documents
        ]
        await asyncio.to_thread(
            self._collection().add,
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        return len(documents)

    async def delete_by_file_id(self, file_id: int) -> None:
        await asyncio.to_thread(
            self._collection().delete, where={"file_id": file_id}
        )

    async def count_by_file_id(self, file_id: int) -> int:
        result = await asyncio.to_thread(
            self._collection().get, where={"file_id": file_id}
        )
        return len(result.get("ids", []))

    async def search(
        self, query: str, top_k: int = 5
    ) -> Sequence[Mapping[str, Any]]:
        query_vector = (await self._embedder.embed([query]))[0]
        result = await asyncio.to_thread(
            self._collection().query,
            query_embeddings=[query_vector],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        return [
            {"content": content, "metadata": dict(metadata), "distance": float(distance)}
            for content, metadata, distance in zip(
                result["documents"][0],
                result["metadatas"][0],
                result["distances"][0],
            )
        ]

    async def close(self) -> None:
        await self._embedder.close()
