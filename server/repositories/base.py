from sqlalchemy.ext.asyncio import AsyncSession


class Repository:
    """Base for every repository; holds the session the request owns."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
