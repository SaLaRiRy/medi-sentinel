"""TICKET-018: the health-record migration bumps the head revision (ADR-0001)."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

SERVER_ROOT = Path(__file__).resolve().parents[1]


def test_upgrade_head_creates_the_health_record_table(tmp_path):
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
            columns = {
                row[1]
                for row in connection.execute(
                    text("PRAGMA table_info(t_health_record)")
                )
            }
    finally:
        engine.dispose()

    assert revision == "0008"
    assert {
        "id",
        "user_id",
        "doctor_id",
        "record_type",
        "diagnosis",
        "treatment",
        "prescription",
        "visit_date",
        "create_time",
        "update_time",
    } <= columns
