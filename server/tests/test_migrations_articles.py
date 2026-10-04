"""TICKET-021: the article/notice migration bumps the head revision (ADR-0001)."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

SERVER_ROOT = Path(__file__).resolve().parents[1]


def _columns(connection, table: str) -> set[str]:
    return {
        row[1] for row in connection.execute(text(f"PRAGMA table_info({table})"))
    }


def test_upgrade_head_creates_the_article_and_notice_tables(tmp_path):
    db_path = tmp_path / "empty.db"
    config = Config(str(SERVER_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            article_columns = _columns(connection, "t_article")
            notice_columns = _columns(connection, "t_notice")
    finally:
        engine.dispose()

    assert revision == "0011"
    assert {
        "id",
        "title",
        "category",
        "cover",
        "summary",
        "content",
        "view_count",
        "status",
        "create_time",
        "update_time",
    } <= article_columns
    assert {
        "id",
        "title",
        "content",
        "status",
        "create_time",
        "update_time",
    } <= notice_columns
