from fastapi import APIRouter

from api.v1 import chat, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(chat.router)
