"""TICKET-013: the two seeding scripts (`init_graph.py`, `init_knowledge.py`).

Both scripts are exercised with injected stores, so no Neo4j/Chroma/embedding
service is required (SPEC.md 4.1 B-3). The knowledge side runs on migrated
SQLite and asserts the 0→1→2 lifecycle, chunk/vector parity, per-document failure
isolation and the explicit "docs_seed missing" exit.
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
    KnowledgeFileRow,
)
from scripts import init_graph, init_knowledge
from scripts.init_knowledge import DocsSeedDirMissing, seed_knowledge

SERVER_ROOT = Path(__file__).resolve().parents[1]


class InMemoryVectorStore:
    """Counts what was vectorized per file so parity is assertable; `fail_for`
    makes one document's vectorization blow up (single failure isolation)."""

    def __init__(self, *, fail_for=(), on_add=None) -> None:
        self.chunks: dict[int, list[str]] = {}
        self.fail_for = set(fail_for)
        self.on_add = on_add
        self.deleted: list[int] = []

    async def add_chunks(self, *, file_id: int, file_name: str, chunks) -> int:
        if file_name in self.fail_for:
            raise RuntimeError("embedding service unavailable")
        if self.on_add is not None:
            await self.on_add(file_id)
        self.chunks[file_id] = list(chunks)
        return len(chunks)

    async def delete_by_file_id(self, file_id: int) -> None:
        self.deleted.append(file_id)
        self.chunks.pop(file_id, None)

    async def count_by_file_id(self, file_id: int) -> int:
        return len(self.chunks.get(file_id, []))

    async def search(self, query: str, top_k: int = 5):
        return []


@pytest.fixture
def database_url(tmp_path) -> str:
    db_path = tmp_path / "seed.db"
    config = Config(str(SERVER_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    command.upgrade(config, "head")
    return f"sqlite+aiosqlite:///{db_path}"


@pytest.fixture
async def session_factory(database_url):
    engine = create_async_engine(database_url)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def _write_docs(directory: Path, docs: dict[str, str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, content in docs.items():
        (directory / name).write_text(content, encoding="utf-8")


async def _files(session_factory) -> list[KnowledgeFileRow]:
    async with session_factory() as session:
        return list((await session.execute(select(KnowledgeFileRow))).scalars())


async def test_seed_indexes_every_document_and_matches_chunk_with_vector_counts(
    tmp_path, session_factory
):
    docs_dir = tmp_path / "docs_seed"
    _write_docs(
        docs_dir,
        {
            "高血压防治指南.md": "# 高血压\n" + "低盐饮食，规律运动。" * 80,
            "感冒与流感指南.md": "# 感冒\n" + "多饮水，注意休息。" * 60,
        },
    )
    store = InMemoryVectorStore()

    summary = await seed_knowledge(
        session_factory=session_factory, store=store, docs_dir=docs_dir
    )

    assert (summary.processed, summary.skipped, summary.failed) == (2, 0, 0)
    rows = await _files(session_factory)
    assert {row.file_name for row in rows} == {
        "高血压防治指南.md",
        "感冒与流感指南.md",
    }
    for row in rows:
        assert row.vector_status == VECTOR_INDEXED
        assert row.chunk_count > 0
        assert row.chunk_count == await store.count_by_file_id(row.id)
        assert row.chunk_count == len(store.chunks[row.id])


async def test_seed_passes_through_uploaded_then_processing_then_indexed(
    tmp_path, session_factory
):
    docs_dir = tmp_path / "docs_seed"
    _write_docs(
        docs_dir, {"高血压防治指南.md": "低盐饮食，规律运动。" * 80}
    )
    observed: list[int] = []

    async def observe(file_id: int) -> None:
        async with session_factory() as session:
            row = await session.get(KnowledgeFileRow, file_id)
            observed.append(row.vector_status)

    await seed_knowledge(
        session_factory=session_factory,
        store=InMemoryVectorStore(on_add=observe),
        docs_dir=docs_dir,
    )

    # The file is already "处理中" when vectorization starts; it ends "已向量化".
    assert observed == [VECTOR_PROCESSING]
    rows = await _files(session_factory)
    assert rows[0].vector_status == VECTOR_INDEXED


async def test_seed_is_idempotent_by_file_name(tmp_path, session_factory):
    docs_dir = tmp_path / "docs_seed"
    _write_docs(docs_dir, {"糖尿病健康管理.md": "综合管理。" * 120})
    store = InMemoryVectorStore()

    first = await seed_knowledge(
        session_factory=session_factory, store=store, docs_dir=docs_dir
    )
    second = await seed_knowledge(
        session_factory=session_factory, store=store, docs_dir=docs_dir
    )

    assert (first.processed, first.skipped) == (1, 0)
    assert (second.processed, second.skipped, second.failed) == (0, 1, 0)
    assert len(await _files(session_factory)) == 1
    assert store.deleted == []  # a skipped file is not re-vectorized


async def test_one_document_failure_does_not_interrupt_the_rest(
    tmp_path, session_factory, capsys
):
    docs_dir = tmp_path / "docs_seed"
    _write_docs(
        docs_dir,
        {
            "a-高血压.md": "低盐饮食。" * 120,
            "b-坏文档.md": "该文档向量化会失败。" * 120,
            "c-糖尿病.md": "综合管理。" * 120,
        },
    )
    store = InMemoryVectorStore(fail_for={"b-坏文档.md"})

    summary = await seed_knowledge(
        session_factory=session_factory, store=store, docs_dir=docs_dir
    )

    assert (summary.processed, summary.skipped, summary.failed) == (2, 0, 1)
    rows = {row.file_name: row for row in await _files(session_factory)}
    assert rows["a-高血压.md"].vector_status == VECTOR_INDEXED
    assert rows["c-糖尿病.md"].vector_status == VECTOR_INDEXED
    assert rows["b-坏文档.md"].vector_status == VECTOR_FAILED


async def test_missing_docs_directory_raises_instead_of_running_empty(
    tmp_path, session_factory
):
    missing = tmp_path / "nope"

    with pytest.raises(DocsSeedDirMissing):
        await seed_knowledge(
            session_factory=session_factory,
            store=InMemoryVectorStore(),
            docs_dir=missing,
        )


def test_init_knowledge_main_exits_with_a_message_when_docs_seed_is_missing(
    tmp_path, capsys
):
    missing = tmp_path / "docs_seed"

    code = init_knowledge.main(["--docs-dir", str(missing)])

    assert code == 1
    assert str(missing) in capsys.readouterr().err


def test_init_graph_main_reports_the_seeded_counts(capsys):
    from graph.store import GraphStats

    class Store:
        def __init__(self) -> None:
            self.closed = False

        async def ensure_constraints(self, labels):
            return None

        async def merge_nodes(self, label, names):
            return None

        async def merge_relationships(self, rel_type, start_label, end_label, edges):
            return None

        async def stats(self):
            return GraphStats(
                nodes_by_label={"Disease": 3}, relationships_by_type={"HAS_SYMPTOM": 9}
            )

        async def close(self):
            self.closed = True

    store = Store()
    code = init_graph.main(store_factory=lambda settings: store)

    assert code == 0
    out = capsys.readouterr().out
    assert "3" in out and "9" in out
    assert store.closed


def test_init_graph_main_exits_with_a_message_when_the_graph_is_unreachable(capsys):
    def boom(settings):
        raise RuntimeError("bolt connection refused")

    code = init_graph.main(store_factory=boom)

    assert code == 1
    assert "bolt connection refused" in capsys.readouterr().err
