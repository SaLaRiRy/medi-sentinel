from sqlalchemy import text

from repositories.base import Repository


class SystemRepository(Repository):
    async def ping(self) -> bool:
        """Reach the database through the session, so readiness is measured, not assumed."""
        await self._session.execute(text("SELECT 1"))
        return True
