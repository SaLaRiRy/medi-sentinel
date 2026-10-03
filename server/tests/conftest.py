"""Shared account fixtures for the auth/profile seams (TICKET-012).

`database_url` migrates a fresh SQLite database; `accounts` seeds one row per
role plus a couple of disabled rows; `client` starts the real app against them.
"""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models.accounts import AdminRow, DoctorRow, UserRow

SERVER_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def database_url(tmp_path) -> str:
    db_path = tmp_path / "auth.db"
    config = Config(str(SERVER_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    command.upgrade(config, "head")
    return f"sqlite+aiosqlite:///{db_path}"


@pytest.fixture
async def accounts(database_url):
    """Seed one row per table; the same username appears in all three on purpose."""
    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(UserRow(username="shared", password="user-pass", real_name="张三"))
        session.add(
            DoctorRow(username="shared", password="doctor-pass", real_name="李医生")
        )
        session.add(
            AdminRow(username="shared", password="admin-pass", nickname="王管理")
        )
        session.add(UserRow(username="disabled", password="pw1234", status=0))
        session.add(
            AdminRow(username="admin2", password="pw1234", nickname="管二", status=0)
        )
        await session.commit()
    await engine.dispose()


@pytest.fixture
async def client(database_url, accounts):
    from core.config import Settings
    from main import create_app

    app = create_app(Settings(database_url=database_url))
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as http:
            yield http
