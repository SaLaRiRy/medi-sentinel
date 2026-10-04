"""TICKET-019: the doctor-consult migration bumps the head revision (ADR-0001)."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

SERVER_ROOT = Path(__file__).resolve().parents[1]


def _columns(connection, table: str) -> set[str]:
    return {
        row[1] for row in connection.execute(text(f"PRAGMA table_info({table})"))
    }


def test_upgrade_head_creates_the_doctor_consult_tables(tmp_path):
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
            consult_columns = _columns(connection, "t_doctor_consult")
            reply_columns = _columns(connection, "t_doctor_reply")
    finally:
        engine.dispose()

    assert revision == "0009"
    assert {
        "id",
        "user_id",
        "doctor_id",
        "chief_complaint",
        "status",
        "create_time",
        "update_time",
    } <= consult_columns
    assert {
        "id",
        "consult_id",
        "doctor_id",
        "content",
        "create_time",
    } <= reply_columns
