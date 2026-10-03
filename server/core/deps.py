"""FastAPI dependencies that expose the B-5 session and the running settings."""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from db.session import Database


def get_active_settings(request: Request) -> Settings:
    return request.app.state.settings


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One session per request: commit on success, roll back on failure."""
    database: Database = request.app.state.database
    async with database.session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()
