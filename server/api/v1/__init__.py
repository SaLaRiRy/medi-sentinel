from fastapi import APIRouter

from api.v1 import (
    appointments,
    articles,
    auth,
    chat,
    consults,
    departments,
    doctors,
    graph,
    health,
    knowledge,
    notices,
    observability,
    profile,
    records,
    users,
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
api_router.include_router(departments.router)
api_router.include_router(users.router)
api_router.include_router(doctors.router)
api_router.include_router(articles.router)
api_router.include_router(notices.router)
