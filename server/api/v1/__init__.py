from fastapi import APIRouter

from api.v1 import auth, chat, health, knowledge, observability, profile

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(chat.router)
api_router.include_router(observability.router)
api_router.include_router(auth.router)
api_router.include_router(profile.router)
api_router.include_router(knowledge.router)
