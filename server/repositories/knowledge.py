"""B-5: async storage for knowledge files and their chunks (TICKET-013).

The session owns the transaction: nothing here commits, so the seed script (or
an upload request) controls where a document's state changes become visible.
`replace_chunks` is the "+先整体清空再重建" step of re-vectorization
(FUNCTIONAL_SPEC.md 5.6): it never leaves two generations of chunks behind.
"""

from collections.abc import Sequence

from sqlalchemy import delete, func, or_, select

from models.knowledge import (
    VECTOR_INDEXED,
    KnowledgeChunkRow,
    KnowledgeFileRow,
    vector_id_of,
)
from repositories.base import Repository


class KnowledgeRepository(Repository):
    async def find_by_file_name(self, file_name: str) -> KnowledgeFileRow | None:
        """灌数脚本的业务键：同名文件视为已存在（FUNCTIONAL_SPEC.md 6.7）。"""
        return (
            await self._session.execute(
                select(KnowledgeFileRow).where(KnowledgeFileRow.file_name == file_name)
            )
        ).scalar_one_or_none()

    async def find_file(self, file_id: int) -> KnowledgeFileRow | None:
        return await self._session.get(KnowledgeFileRow, file_id)

    def _search_criteria(
        self, keyword: str | None, file_type: str | None
    ) -> list:
        criteria = []
        if keyword:
            pattern = f"%{keyword}%"
            criteria.append(
                or_(
                    KnowledgeFileRow.file_name.like(pattern),
                    KnowledgeFileRow.file_type.like(pattern),
                )
            )
        if file_type:
            criteria.append(KnowledgeFileRow.file_type == file_type)
        return criteria

    async def list_files(
        self,
        *,
        offset: int,
        limit: int,
        keyword: str | None = None,
        file_type: str | None = None,
    ) -> tuple[list[KnowledgeFileRow], int]:
        """分页列表；`keyword` 同时模糊匹配文件名与类型（FUNCTIONAL_SPEC 2.3）。"""
        criteria = self._search_criteria(keyword, file_type)
        total = int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(KnowledgeFileRow)
                    .where(*criteria)
                )
            ).scalar_one()
        )
        rows = (
            (
                await self._session.execute(
                    select(KnowledgeFileRow)
                    .where(*criteria)
                    .order_by(KnowledgeFileRow.id.desc())
                    .offset(offset)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), total

    async def create_file(
        self,
        *,
        file_name: str,
        file_type: str,
        file_size: int,
        file_path: str,
        upload_by: int | None = None,
        upload_role: str = "admin",
    ) -> KnowledgeFileRow:
        """新建文件记录，初始状态为 0「已上传」（FUNCTIONAL_SPEC.md 5.6）。"""
        row = KnowledgeFileRow(
            file_name=file_name,
            file_type=file_type,
            file_size=file_size,
            file_path=file_path,
            upload_by=upload_by,
            upload_role=upload_role,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def set_status(self, file_id: int, status: int) -> None:
        row = await self._session.get(KnowledgeFileRow, file_id)
        if row is None:
            raise LookupError(f"知识库文件不存在：{file_id}")
        row.vector_status = status

    async def mark_indexed(self, file_id: int, *, chunk_count: int) -> None:
        """记录分块数并把状态置为 2「已向量化」（FUNCTIONAL_SPEC.md 5.6）。"""
        row = await self._session.get(KnowledgeFileRow, file_id)
        if row is None:
            raise LookupError(f"知识库文件不存在：{file_id}")
        row.chunk_count = chunk_count
        row.vector_status = VECTOR_INDEXED

    async def replace_chunks(
        self, file_id: int, chunks: Sequence[str]
    ) -> list[KnowledgeChunkRow]:
        """整体清空该文件的旧分块后重建；序号从 0 起，`vector_id` 随之生成。"""
        await self._session.execute(
            delete(KnowledgeChunkRow).where(KnowledgeChunkRow.file_id == file_id)
        )
        rows = [
            KnowledgeChunkRow(
                file_id=file_id,
                chunk_index=index,
                content=content,
                vector_id=vector_id_of(file_id, index),
            )
            for index, content in enumerate(chunks)
        ]
        self._session.add_all(rows)
        await self._session.flush()
        return rows

    async def chunk_count(self, file_id: int) -> int:
        return int(
            (
                await self._session.execute(
                    select(func.count())
                    .select_from(KnowledgeChunkRow)
                    .where(KnowledgeChunkRow.file_id == file_id)
                )
            ).scalar_one()
        )

    async def delete_chunks(self, file_id: int) -> None:
        """删除该文件的全部旧分块（FUNCTIONAL_SPEC.md 5.6 级联删除第 2 步）。"""
        await self._session.execute(
            delete(KnowledgeChunkRow).where(KnowledgeChunkRow.file_id == file_id)
        )

    async def delete_file(self, file_id: int) -> None:
        """删除文件记录；记录不存在时同样返回成功（FUNCTIONAL_SPEC.md 5.6）。"""
        row = await self._session.get(KnowledgeFileRow, file_id)
        if row is not None:
            await self._session.delete(row)
