"""B-5: the per-request session commits on success and rolls back on failure.

The probe table is created by the test itself, so this exercises the seam
without inventing a domain entity the skeleton does not own yet.
"""

from types import SimpleNamespace

import pytest
from sqlalchemy import text

from core.deps import get_session
from db.session import Database


def _request_for(database: Database) -> SimpleNamespace:
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(database=database)))


@pytest.fixture
async def database(tmp_path):
    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'seam.db'}")
    async with db.engine.begin() as connection:
        await connection.execute(text("CREATE TABLE probe (id INTEGER PRIMARY KEY)"))
    yield db
    await db.dispose()


async def _probe_ids(database: Database) -> list[int]:
    async with database.engine.connect() as connection:
        result = await connection.execute(text("SELECT id FROM probe ORDER BY id"))
        return list(result.scalars())


async def test_session_commits_when_the_request_succeeds(database):
    dependency = get_session(_request_for(database))
    session = await dependency.__anext__()
    await session.execute(text("INSERT INTO probe (id) VALUES (1)"))

    with pytest.raises(StopAsyncIteration):
        await dependency.__anext__()

    assert await _probe_ids(database) == [1]


async def test_session_rolls_back_when_the_request_fails(database):
    dependency = get_session(_request_for(database))
    session = await dependency.__anext__()
    await session.execute(text("INSERT INTO probe (id) VALUES (2)"))

    with pytest.raises(RuntimeError, match="boom"):
        await dependency.athrow(RuntimeError("boom"))

    assert await _probe_ids(database) == []
