from fastapi import APIRouter

from api.v1 import (
    appointments,
    auth,
    chat,
    consults,
    graph,
    health,
    knowledge,
    observability,
    profile,
    records,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(chat.router)
api_router.include_router(observability.router)
api_router.include_router(auth.router)
api_router.include_router(profile.router)
api_router.include_router(knowledge.router)
api_router.include_router(graph.router)
api_router.include_router(appointments.router)
api_router.include_router(records.router)
api_router.include_router(consults.router)
