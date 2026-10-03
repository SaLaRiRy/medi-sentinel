from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from core.deps import get_active_settings, get_session
from core.response import Envelope, success
from repositories.system import SystemRepository

router = APIRouter(tags=["health"])


class HealthData(BaseModel):
    status: str
    database: str
    version: str


@router.get("/health", response_model=Envelope[HealthData])
async def read_health(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_active_settings),
) -> Envelope[HealthData]:
    database = "ok"
    try:
        await SystemRepository(session).ping()
    except SQLAlchemyError:
        database = "unavailable"
    return success(HealthData(status="ok", database=database, version=settings.version))
