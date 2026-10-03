from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.v1 import api_router
from core.config import Settings, get_settings
from core.errors import register_error_handlers
from core.response import EnvelopeJSONResponse
from db.session import Database
from services.generation import SessionGenerationGuard
from skills.orchestration import OrchestrationPorts
from skills.ports import (
    UnavailableGraphPort,
    UnavailableLlmPort,
    UnavailableRetrievalPort,
)


def create_app(
    settings: Settings | None = None, ports: OrchestrationPorts | None = None
) -> FastAPI:
    active_settings = settings or get_settings()
    # Real graph / retrieval / model adapters land with the stores they talk to
    # (TICKET-013 / 015); until then the branches degrade and generation errors
    # instead of the process crashing, and tests inject B-3 fakes.
    active_ports = ports or OrchestrationPorts(
        graph=UnavailableGraphPort(),
        retrieval=UnavailableRetrievalPort(),
        llm=UnavailableLlmPort(),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = active_settings
        app.state.database = Database(active_settings.database_url)
        app.state.orchestration_ports = active_ports
        app.state.generation_guard = SessionGenerationGuard()
        _prepare_uploads(app, active_settings)
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


def _prepare_uploads(app: FastAPI, settings: Settings) -> None:
    """Create the upload layout and serve it (FUNCTIONAL_SPEC 5.18).

    A read-only or sandboxed filesystem must not stop the app from starting, so
    the mount is skipped when the directory cannot be created.
    """
    root = Path(settings.upload_dir)
    try:
        (root / settings.avatar_subdir).mkdir(parents=True, exist_ok=True)
        (root / "knowledge").mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    if root.is_dir():
        app.mount(
            settings.uploads_url_prefix,
            StaticFiles(directory=root),
            name="uploads",
        )


app = create_app()
