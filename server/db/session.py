"""B-5: async engine plus a session factory, handed to repositories per request."""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class Database:
    def __init__(self, url: str) -> None:
        if not url:
            raise ValueError(
                "DATABASE_URL 未配置：请在 server/.env 中设置 DATABASE_URL"
                "（例如 mysql+aiomysql://<user>:<password>@127.0.0.1:3306/medi_sentinel）。"
            )
        self._engine: AsyncEngine = create_async_engine(url, pool_pre_ping=True)
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self._engine, expire_on_commit=False
        )

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    async def dispose(self) -> None:
        await self._engine.dispose()
