from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from adapters import build_graph_store, build_vector_store
from api.v1 import api_router
from core.config import Settings, get_settings
from core.errors import register_error_handlers
from core.response import EnvelopeJSONResponse
from db.session import Database
from services.generation import SessionGenerationGuard
from services.knowledge import KnowledgeJobs
from skills.orchestration import OrchestrationPorts
from skills.ports import UnavailableLlmPort


def create_app(
    settings: Settings | None = None, ports: OrchestrationPorts | None = None
) -> FastAPI:
    active_settings = settings or get_settings()
    # TICKET-013 wired the real async graph and vector stores (SPEC.md 3.1): they
    # degrade the branch when unreachable rather than crashing. The model adapter
    # is still pending, so generation ends in an `error` frame; tests inject B-3
    # fakes instead.
    active_ports = ports or OrchestrationPorts(
        graph=build_graph_store(active_settings),
        retrieval=build_vector_store(active_settings),
        llm=UnavailableLlmPort(),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = active_settings
        app.state.database = Database(active_settings.database_url)
        app.state.orchestration_ports = active_ports
        app.state.generation_guard = SessionGenerationGuard()
        app.state.knowledge_jobs = KnowledgeJobs(
            session_factory=app.state.database.session_factory,
            store=active_ports.retrieval,
        )
        _prepare_uploads(app, active_settings)
        yield
        for port in (active_ports.graph, active_ports.retrieval):
            close = getattr(port, "close", None)
            if callable(close):
                await close()
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
        (root / settings.knowledge_subdir).mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    if root.is_dir():
        app.mount(
            settings.uploads_url_prefix,
            StaticFiles(directory=root),
            name="uploads",
        )


app = create_app()
