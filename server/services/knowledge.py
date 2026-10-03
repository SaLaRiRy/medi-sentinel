"""知识库生命周期任务（TICKET-015，`FUNCTIONAL_SPEC.md` 5.6）。

一个文件从「已上传」到「已向量化」的全部副作用都在这里：状态置 1 → 解析 →
分块 → 先清旧分块与旧向量 → 写新分块 → 写向量 → 校验分块数与向量条目数一致
→ 状态置 2；任一环节异常则状态置 3「失败」并允许重新向量化。

任务自带会话（`session_factory`），不复用请求的 `AsyncSession`：上传接口
必须立即返回，向量化在后台跑，而每请求一个会话的约束只约束请求路径
（SPEC.md 3.1）。写向量与写分块都不在同一个事务里，因此失败后必须由
重新向量化整体重建，而不是在旧数据上打补丁。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

import anyio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from models.knowledge import VECTOR_FAILED, VECTOR_PROCESSING
from rag.chunking import split_text
from rag.loader import load_document
from rag.store import VectorStore
from repositories.knowledge import KnowledgeRepository

logger = logging.getLogger(__name__)

DocumentLoader = Callable[[Path], str]
JobScheduler = Callable[[Coroutine[Any, Any, None]], "asyncio.Task[None]"]


class KnowledgeJobs:
    """The knowledge-base job seam: one file id in, one vectorized file out."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        store: VectorStore,
        loader: DocumentLoader = load_document,
        scheduler: JobScheduler | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._store = store
        self._loader = loader
        self._scheduler: JobScheduler = scheduler or asyncio.create_task
        self._tasks: set[asyncio.Task[None]] = set()

    def schedule_vectorize(self, file_id: int) -> None:
        """Fire-and-forget the job so an upload returns before vectorization."""
        job = self._scheduler(self.vectorize(file_id))
        self._tasks.add(job)
        add_done_callback = getattr(job, "add_done_callback", None)
        if callable(add_done_callback):
            add_done_callback(self._tasks.discard)

    async def delete(
        self, file_id: int, *, session: AsyncSession | None = None
    ) -> bool:
        """删向量索引 → 删分块记录 → 删磁盘文件（存在时）→ 删文件记录。

        Returns whether the file existed. A request-scoped caller passes its own
        `AsyncSession` so the whole deletion stays in one transaction (SPEC.md 3.1);
        the standalone path opens and commits its own.
        """
        if session is None:
            async with self._session_factory() as own:
                deleted = await self._delete_with(own, file_id)
                await own.commit()
                return deleted
        return await self._delete_with(session, file_id)

    async def _delete_with(self, session: AsyncSession, file_id: int) -> bool:
        repository = KnowledgeRepository(session)
        row = await repository.find_file(file_id)
        if row is None:
            return False
        file_path = Path(row.file_path)
        await self._store.delete_by_file_id(file_id)
        await repository.delete_chunks(file_id)
        if file_path.exists():
            await anyio.to_thread.run_sync(file_path.unlink)
        await repository.delete_file(file_id)
        return True

    async def vectorize(self, file_id: int) -> None:
        try:
            async with self._session_factory() as session:
                repository = KnowledgeRepository(session)
                row = await repository.find_file(file_id)
                if row is None:
                    return
                file_path, file_name = row.file_path, row.file_name
                await repository.set_status(file_id, VECTOR_PROCESSING)
                await session.commit()

            chunks = split_text(self._loader(Path(file_path)))
            await self._store.delete_by_file_id(file_id)
            async with self._session_factory() as session:
                await KnowledgeRepository(session).replace_chunks(file_id, chunks)
                await session.commit()

            stored = await self._store.add_chunks(
                file_id=file_id, file_name=file_name, chunks=chunks
            )
            indexed = await self._store.count_by_file_id(file_id)
            if stored != len(chunks) or indexed != len(chunks):
                raise RuntimeError(
                    f"分块数与向量条目数不一致：分块 {len(chunks)}，向量 {indexed}"
                )

            async with self._session_factory() as session:
                await KnowledgeRepository(session).mark_indexed(
                    file_id, chunk_count=len(chunks)
                )
                await session.commit()
        except Exception:
            logger.exception("knowledge vectorization failed for file %s", file_id)
            try:
                async with self._session_factory() as session:
                    await KnowledgeRepository(session).set_status(
                        file_id, VECTOR_FAILED
                    )
                    await session.commit()
            except Exception:  # noqa: BLE001 - the row may already be gone
                logger.exception("failed to mark knowledge file %s as failed", file_id)
