"""TICKET-013: the knowledge-base store — chunking, tables and repository.

Spec source: FUNCTIONAL_SPEC.md 4.3.13 / 4.3.14 (KnowledgeFile / KnowledgeChunk),
5.5 (500/80 chunking, separator priority) and 5.6 (the 0→1→2 vectorization
lifecycle). Storage runs on a migrated SQLite database; no vector index needed.
"""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models.knowledge import (
    VECTOR_FAILED,
    VECTOR_INDEXED,
    VECTOR_PROCESSING,
    VECTOR_UPLOADED,
    KnowledgeChunkRow,
    KnowledgeFileRow,
    vector_id_of,
)
from rag.chunking import CHUNK_OVERLAP, CHUNK_SIZE, split_text
from repositories.knowledge import KnowledgeRepository

SERVER_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def database_url(tmp_path) -> str:
    db_path = tmp_path / "knowledge.db"
    config = Config(str(SERVER_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    command.upgrade(config, "head")
    return f"sqlite+aiosqlite:///{db_path}"


@pytest.fixture
async def session_factory(database_url):
    engine = create_async_engine(database_url)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


# --- chunking (pure CPU) -----------------------------------------------------


def test_split_text_returns_the_single_piece_when_it_fits():
    assert split_text("短句。") == ["短句。"], f"chunk_size={CHUNK_SIZE}"


def test_split_text_merges_pieces_up_to_the_chunk_size_with_overlap():
    text = "aa bb cc dd ee ff gg"

    chunks = split_text(text, chunk_size=10, chunk_overlap=3)

    assert chunks == ["aa bb cc ", "cc dd ee ", "ee ff gg"]
    assert all(len(chunk) <= 10 for chunk in chunks)


def test_split_text_hard_splits_when_no_separator_remains():
    chunks = split_text("x" * 25, chunk_size=10, chunk_overlap=3)

    assert [len(chunk) for chunk in chunks] == [10, 10, 8]
    assert all(len(chunk) <= 10 for chunk in chunks)


def test_split_text_never_exceeds_the_default_chunk_size_on_a_seed_document():
    content = (SERVER_ROOT / "docs_seed" / "高血压防治指南.md").read_text(
        encoding="utf-8"
    )

    chunks = split_text(content)
    longer = split_text(content * 3)

    assert all(0 < len(chunk) <= CHUNK_SIZE for chunk in chunks)
    assert all(0 < len(chunk) <= CHUNK_SIZE for chunk in longer)
    assert len(longer) > 1
    assert CHUNK_OVERLAP < CHUNK_SIZE


# --- tables ------------------------------------------------------------------


def test_the_migration_creates_the_knowledge_tables(database_url):
    from sqlalchemy import create_engine, text

    db_path = database_url.removeprefix("sqlite+aiosqlite:///")
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as connection:
            tables = set(
                connection.execute(
                    text("SELECT name FROM sqlite_master WHERE type = 'table'")
                )
                .scalars()
                .all()
            )
    finally:
        engine.dispose()

    assert {"t_knowledge_file", "t_knowledge_chunk"} <= tables


def test_vector_status_values_match_the_reference_lifecycle():
    assert (VECTOR_UPLOADED, VECTOR_PROCESSING, VECTOR_INDEXED, VECTOR_FAILED) == (
        0,
        1,
        2,
        3,
    )


def test_vector_id_follows_the_documented_format():
    assert vector_id_of(7, 3) == "file_7_chunk_3"


# --- repository --------------------------------------------------------------


async def _seed_file(session_factory) -> int:
    async with session_factory() as session:
        row = await KnowledgeRepository(session).create_file(
            file_name="高血压防治指南.md",
            file_type="md",
            file_size=100,
            file_path="D:/uploads33/knowledge/高血压防治指南.md",
        )
        await session.commit()
        return row.id


async def test_create_file_starts_in_the_uploaded_state(session_factory):
    async with session_factory() as session:
        row = await KnowledgeRepository(session).create_file(
            file_name="感冒与流感指南.md",
            file_type="md",
            file_size=10,
            file_path="/tmp/感冒与流感指南.md",
        )

        assert row.vector_status == VECTOR_UPLOADED
        assert row.chunk_count == 0


async def test_find_by_file_name_is_the_idempotency_key(session_factory):
    file_id = await _seed_file(session_factory)

    async with session_factory() as session:
        repository = KnowledgeRepository(session)
        found = await repository.find_by_file_name("高血压防治指南.md")
        missing = await repository.find_by_file_name("不存在.md")

    assert found is not None and found.id == file_id
    assert missing is None


async def test_replace_chunks_rebuilds_the_chunk_set_with_vector_ids(session_factory):
    file_id = await _seed_file(session_factory)

    async with session_factory() as session:
        repository = KnowledgeRepository(session)
        await repository.replace_chunks(file_id, ["第一块", "第二块"])
        await repository.replace_chunks(file_id, ["唯一块"])
        await session.commit()

    async with session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(KnowledgeChunkRow).where(
                        KnowledgeChunkRow.file_id == file_id
                    )
                )
            )
            .scalars()
            .all()
        )

    assert [(row.chunk_index, row.content, row.vector_id) for row in rows] == [
        (0, "唯一块", vector_id_of(file_id, 0))
    ]


async def test_mark_indexed_sets_the_status_and_chunk_count(session_factory):
    file_id = await _seed_file(session_factory)

    async with session_factory() as session:
        await KnowledgeRepository(session).mark_indexed(file_id, chunk_count=4)
        await session.commit()

    async with session_factory() as session:
        row = await session.get(KnowledgeFileRow, file_id)

    assert row.vector_status == VECTOR_INDEXED
    assert row.chunk_count == 4
