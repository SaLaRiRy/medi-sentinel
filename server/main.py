from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v1 import api_router
from core.config import Settings, get_settings
from core.errors import register_error_handlers
from core.response import EnvelopeJSONResponse
from db.session import Database


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = active_settings
        app.state.database = Database(active_settings.database_url)
        yield
        await app.state.database.dispose()

    app = FastAPI(
        title=active_settings.project_name,
        version=active_settings.version,
        lifespan=lifespan,
        default_response_class=EnvelopeJSONResponse,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.cors_allow_origins,
        allow_credentials=active_settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(api_router, prefix=active_settings.api_prefix)
    return app


app = create_app()
