"""知识库种子文档灌入并向量化（TICKET-013，幂等）。

Run from `server/`:  .venv\\Scripts\\python.exe scripts\\init_knowledge.py

按文件名跳过已存在的记录（`FUNCTIONAL_SPEC.md` 6.7）；逐篇把状态从 0「已上传」
推到 1「处理中」再推到 2「已向量化」，并校验分块数与向量条目数一致。单篇失败
置为 3「失败」且不中断其余文档；`server/docs_seed/` 缺失时明确提示并退出。
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_ROOT))

from collections.abc import Callable  # noqa: E402

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker  # noqa: E402

from adapters import build_vector_store  # noqa: E402
from core.config import Settings, get_settings  # noqa: E402
from db.session import Database  # noqa: E402
from models.knowledge import (  # noqa: E402
    VECTOR_FAILED,
    VECTOR_PROCESSING,
)
from rag.chunking import split_text  # noqa: E402
from rag.store import VectorStore  # noqa: E402
from repositories.knowledge import KnowledgeRepository  # noqa: E402

DOC_SUFFIXES = (".md", ".txt")
DEFAULT_DOCS_DIR = SERVER_ROOT / "docs_seed"

StoreFactory = Callable[[Settings], VectorStore]
SessionFactory = async_sessionmaker[AsyncSession]


class DocsSeedDirMissing(FileNotFoundError):
    """`server/docs_seed/` 不存在：脚本必须明确提示并退出，而不是静默空跑。"""


@dataclass(frozen=True)
class SeedSummary:
    processed: int
    skipped: int
    failed: int


def _read_document(path: Path) -> str:
    if path.suffix.lower() not in DOC_SUFFIXES:
        raise ValueError(f"不支持的种子文档类型：{path.suffix}")
    return path.read_text(encoding="utf-8")


def _documents(docs_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in docs_dir.iterdir()
        if path.is_file() and path.suffix.lower() in DOC_SUFFIXES
    )


async def seed_knowledge(
    *,
    session_factory: SessionFactory,
    store: VectorStore,
    docs_dir: Path,
) -> SeedSummary:
    if not docs_dir.is_dir():
        raise DocsSeedDirMissing(str(docs_dir))

    processed = skipped = failed = 0
    for path in _documents(docs_dir):
        file_name = path.name
        async with session_factory() as session:
            repository = KnowledgeRepository(session)
            if await repository.find_by_file_name(file_name) is not None:
                skipped += 1
                continue
            row = await repository.create_file(
                file_name=file_name,
                file_type=path.suffix.lstrip(".").lower(),
                file_size=path.stat().st_size,
                file_path=str(path),
            )
            file_id = row.id
            await session.commit()

        try:
            async with session_factory() as session:
                await KnowledgeRepository(session).set_status(
                    file_id, VECTOR_PROCESSING
                )
                await session.commit()

            chunks = split_text(_read_document(path))
            async with session_factory() as session:
                await KnowledgeRepository(session).replace_chunks(file_id, chunks)
                await session.commit()

            stored = await store.add_chunks(
                file_id=file_id, file_name=file_name, chunks=chunks
            )
            indexed = await store.count_by_file_id(file_id)
            if stored != len(chunks) or indexed != len(chunks):
                raise RuntimeError(
                    f"分块数与向量条目数不一致：分块 {len(chunks)}，向量 {indexed}"
                )

            async with session_factory() as session:
                await KnowledgeRepository(session).mark_indexed(
                    file_id, chunk_count=len(chunks)
                )
                await session.commit()
            processed += 1
        except Exception as error:  # noqa: BLE001 - 单篇失败不中断其余文档
            failed += 1
            print(
                f"知识文档灌入失败：{file_name}：{type(error).__name__}: {error}",
                file=sys.stderr,
            )
            async with session_factory() as session:
                await KnowledgeRepository(session).set_status(file_id, VECTOR_FAILED)
                await session.commit()

    return SeedSummary(processed=processed, skipped=skipped, failed=failed)


async def _run(
    *,
    session_factory: SessionFactory,
    store: VectorStore,
    docs_dir: Path,
    database: Database | None,
) -> SeedSummary:
    try:
        return await seed_knowledge(
            session_factory=session_factory, store=store, docs_dir=docs_dir
        )
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            await close()
        if database is not None:
            await database.dispose()


def main(
    argv: list[str] | None = None,
    *,
    store_factory: StoreFactory | None = None,
    session_factory: SessionFactory | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="灌入知识库种子文档并向量化（幂等）")
    parser.add_argument(
        "--docs-dir",
        default=str(DEFAULT_DOCS_DIR),
        help="种子文档目录，默认 server/docs_seed/",
    )
    args = parser.parse_args(argv)
    docs_dir = Path(args.docs_dir)
    if not docs_dir.is_dir():
        print(
            f"种子文档目录不存在：{docs_dir}。"
            "请在 server/docs_seed/ 放置 .md/.txt 文档后重试。",
            file=sys.stderr,
        )
        return 1

    settings = get_settings()
    database: Database | None = None
    if session_factory is None:
        database = Database(settings.database_url)
        session_factory = database.session_factory
    store = (store_factory or build_vector_store)(settings)

    try:
        summary = asyncio.run(
            _run(
                session_factory=session_factory,
                store=store,
                docs_dir=docs_dir,
                database=database,
            )
        )
    except Exception as error:
        print(f"知识库灌数失败：{type(error).__name__}: {error}", file=sys.stderr)
        return 1

    print(
        "知识库灌数完成："
        f"成功 {summary.processed} 篇，跳过 {summary.skipped} 篇，失败 {summary.failed} 篇"
    )
    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
