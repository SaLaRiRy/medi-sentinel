"""TICKET-015: the knowledge-base lifecycle job (B-5, SPEC.md 5.4 / FUNCTIONAL_SPEC 5.6).

The seam under test is the job itself: a `KnowledgeFile` row plus a vector store
go in; the row's `vector_status` / `chunk_count` and the store's contents come
out. A migrated SQLite database and an in-memory vector store keep it off the
network, so the 0 → 1 → 2 / 3 machine is observable without Chroma or an
embedding service.
"""

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models.knowledge import (
    VECTOR_FAILED,
    VECTOR_INDEXED,
    VECTOR_PROCESSING,
    VECTOR_UPLOADED,
    KnowledgeChunkRow,
    KnowledgeFileRow,
)
from rag.chunking import split_text
from rag.loader import DocumentParseError, UnsupportedDocumentType, load_document
from repositories.knowledge import KnowledgeRepository
from services.knowledge import KnowledgeJobs
from tests.doubles import InMemoryVectorStore


@pytest.fixture
async def session_factory(database_url):
    engine = create_async_engine(database_url)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _add_file(session_factory, path: Path, *, name: str = "指南.md") -> int:
    async with session_factory() as session:
        row = await KnowledgeRepository(session).create_file(
            file_name=name,
            file_type=path.suffix.lstrip("."),
            file_size=path.stat().st_size,
            file_path=str(path),
        )
        await session.commit()
        return row.id


async def _file(session_factory, file_id: int) -> KnowledgeFileRow:
    async with session_factory() as session:
        row = await session.get(KnowledgeFileRow, file_id)
        assert row is not None
        return row


async def _status_at_add(session_factory, file_id: int) -> int:
    """Read the status from a *separate* session while the job is mid-flight."""

    async def read() -> int:
        async with session_factory() as session:
            row = await session.get(KnowledgeFileRow, file_id)
            assert row is not None
            return row.vector_status

    return await read()


async def test_vectorize_moves_a_file_from_uploaded_to_indexed(
    session_factory, tmp_path
):
    document = tmp_path / "指南.md"
    document.write_text("高血压。\n\n请按时服药。" * 60, encoding="utf-8")
    file_id = await _add_file(session_factory, document)
    store = InMemoryVectorStore()
    jobs = KnowledgeJobs(session_factory=session_factory, store=store)
    observed: list[int] = []

    async def record_status() -> None:
        observed.append(await _status_at_add(session_factory, file_id))

    store.on_add = record_status

    await jobs.vectorize(file_id)

    expected_chunks = split_text(document.read_text(encoding="utf-8"))
    row = await _file(session_factory, file_id)
    assert observed == [VECTOR_PROCESSING]
    assert row.vector_status == VECTOR_INDEXED
    assert row.chunk_count == len(expected_chunks)
    assert await store.count_by_file_id(file_id) == len(expected_chunks)


async def _find_file(session_factory, file_id: int) -> KnowledgeFileRow | None:
    async with session_factory() as session:
        return await session.get(KnowledgeFileRow, file_id)


async def _chunk_count(session_factory, file_id: int) -> int:
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(KnowledgeChunkRow).where(KnowledgeChunkRow.file_id == file_id)
            )
        ).scalars()
        return len(list(rows))


async def test_delete_removes_vectors_chunks_disk_file_and_row(
    session_factory, tmp_path
):
    document = tmp_path / "指南.md"
    document.write_text("高血压。\n\n请按时服药。" * 60, encoding="utf-8")
    file_id = await _add_file(session_factory, document)
    store = InMemoryVectorStore()
    jobs = KnowledgeJobs(session_factory=session_factory, store=store)
    await jobs.vectorize(file_id)
    assert await _chunk_count(session_factory, file_id) > 0

    await jobs.delete(file_id)

    assert await store.count_by_file_id(file_id) == 0
    assert file_id in store.deleted
    assert await _chunk_count(session_factory, file_id) == 0
    assert not document.exists()
    assert await _find_file(session_factory, file_id) is None


async def test_delete_of_a_missing_file_is_a_no_op(session_factory):
    store = InMemoryVectorStore()
    jobs = KnowledgeJobs(session_factory=session_factory, store=store)

    await jobs.delete(404)

    assert store.deleted == []


def test_loader_decodes_text_and_refuses_unknown_suffixes(tmp_path):
    plain = tmp_path / "指南.md"
    plain.write_text("高血压防治", encoding="utf-8")
    legacy = tmp_path / "指南.txt"
    legacy.write_bytes("高血压防治".encode("gbk"))

    assert load_document(plain) == "高血压防治"
    assert load_document(legacy) == "高血压防治"
    with pytest.raises(UnsupportedDocumentType):
        load_document(tmp_path / "笔记.exe")


def test_loader_reports_unparsable_pdf_and_docx_as_parse_failures(tmp_path):
    pdf = tmp_path / "指南.pdf"
    pdf.write_bytes(b"%PDF-1.4 not really a pdf")
    docx = tmp_path / "指南.docx"
    docx.write_bytes(b"not a zip archive")

    with pytest.raises(DocumentParseError):
        load_document(pdf)
    with pytest.raises(DocumentParseError):
        load_document(docx)


async def test_a_failed_parse_can_be_recovered_by_revectorizing(
    session_factory, tmp_path
):
    document = tmp_path / "指南.md"
    document.write_text("高血压。\n\n请按时服药。" * 60, encoding="utf-8")
    file_id = await _add_file(session_factory, document)
    store = InMemoryVectorStore()
    jobs = KnowledgeJobs(session_factory=session_factory, store=store)
    document.unlink()

    await jobs.vectorize(file_id)

    assert (await _file(session_factory, file_id)).vector_status == VECTOR_FAILED
    assert await store.count_by_file_id(file_id) == 0

    document.write_text("高血压。\n\n请按时服药。" * 60, encoding="utf-8")
    await jobs.vectorize(file_id)

    row = await _file(session_factory, file_id)
    assert row.vector_status == VECTOR_INDEXED
    assert row.chunk_count == await store.count_by_file_id(file_id)
