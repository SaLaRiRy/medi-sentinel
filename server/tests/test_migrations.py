"""B-5 + ADR-0001: an empty database reaches the full schema via `alembic upgrade head`,
and running it again changes nothing.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

SERVER_ROOT = Path(__file__).resolve().parents[1]


def _config(db_path: Path) -> Config:
    config = Config(str(SERVER_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    return config


def _stamped_revisions(db_path: Path) -> list[str]:
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as connection:
            return list(
                connection.execute(text("SELECT version_num FROM alembic_version"))
                .scalars()
                .all()
            )
    finally:
        engine.dispose()


def test_upgrade_head_brings_an_empty_database_to_the_current_revision(tmp_path):
    db_path = tmp_path / "empty.db"

    command.upgrade(_config(db_path), "head")

    assert _stamped_revisions(db_path) == ["0009"]


def test_upgrade_head_twice_is_a_no_op(tmp_path):
    db_path = tmp_path / "empty.db"
    config = _config(db_path)

    command.upgrade(config, "head")
    command.upgrade(config, "head")

    assert _stamped_revisions(db_path) == ["0009"]


def test_upgrade_head_adds_the_trace_span_detail_column(tmp_path):
    """TICKET-011: the structured detail column lands with the model (ADR-0001)."""
    db_path = tmp_path / "empty.db"

    command.upgrade(_config(db_path), "head")

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as connection:
            columns = {
                row[1]
                for row in connection.execute(text("PRAGMA table_info(trace_span)"))
            }
    finally:
        engine.dispose()

    assert "detail" in columns


def test_upgrade_head_creates_the_trace_store(tmp_path):
    db_path = tmp_path / "empty.db"

    command.upgrade(_config(db_path), "head")

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

    assert {"trace_span", "route_decision"} <= tables


def test_upgrade_head_creates_the_consult_store(tmp_path):
    db_path = tmp_path / "empty.db"

    command.upgrade(_config(db_path), "head")

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

    assert {"t_consult_session", "t_consult_message"} <= tables


def test_upgrade_head_creates_the_three_account_tables(tmp_path):
    """TICKET-012: the token layer needs one table per role (FUNCTIONAL_SPEC 4.3.1-4.3.3)."""
    db_path = tmp_path / "empty.db"

    command.upgrade(_config(db_path), "head")

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

    assert {"t_admin", "t_user", "t_doctor"} <= tables
