import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.core.logging_config import setup_logging
from app.core.config import settings

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
setup_logging()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan: startup / shutdown hooks
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Automated Test-Generation API starting up …")

    # Start background monitoring loop
    import asyncio
    from app.services.monitoring_service import monitoring_loop
    monitor_task = asyncio.create_task(monitoring_loop())

    # Create all tables (idempotent — safe to call every startup)
    try:
        from app.db.database import engine

        # 1. Auth tables (users, ingestion_jobs — AuthBase)
        from app.models.user_model import AuthBase
        from app.models.job_model import IngestionJob  # noqa: F401
        async with engine.begin() as conn:
            await conn.run_sync(AuthBase.metadata.create_all)

        # 2. Platform tables (repositories, jobs, webhook_events, etc — Base)
        from app.db.base import Base
        from app.db.models import (  # noqa: F401 — side-effect imports
            User as PgUser, Repository, Job, WebhookEvent,
            GeneratedTest, ValidationRun,
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database initialized successfully.")
    except Exception as exc:
        logger.error("Database initialization failed: %s", exc)
        logger.error("The API will start but database operations will fail.")

    yield

    logger.info("Automated Test-Generation API shutting down …")
    monitor_task.cancel()
    try:
        from app.db.database import dispose_engine
        await dispose_engine()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Automated Test-Generation API",
    description=(
        "Polyglot, diff-aware test generation service.\n\n"
        "**Workflow**\n"
        "1. `/repos/clone-and-index` — clone a repo and embed it into ChromaDB\n"
        "2. `/repos/diff-pipeline`   — analyse the latest git diff and get LLM prompts\n"
        "3. `/repos/update`          — incrementally re-embed only changed files\n"
        "4. `/repos/query`           — semantic search over an indexed codebase\n"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled exception on %s %s: %s\n%s",
        request.method,
        request.url.path,
        exc,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected internal error occurred."},
    )


@app.exception_handler(OperationalError)
async def database_exception_handler(request: Request, exc: OperationalError) -> JSONResponse:
    logger.error("Database error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "Database is unavailable."},
    )


# ---------------------------------------------------------------------------
# Routers — import with error handling so one broken router doesn't kill the app
# ---------------------------------------------------------------------------
def _mount_router(module_path: str, attr: str = "router"):
    """Import a router module and mount it, logging errors instead of crashing."""
    try:
        import importlib
        mod = importlib.import_module(module_path)
        router = getattr(mod, attr)
        app.include_router(router)
        logger.debug("Mounted router: %s", module_path)
    except Exception as exc:
        logger.error("Failed to mount router %s: %s", module_path, exc)


_mount_router("app.routes.auth_routes")
_mount_router("app.routes.job_routes")
_mount_router("app.routes.webhook_routes")
_mount_router("app.api.routes.repo_routes")
_mount_router("app.api.routes.test_routes")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["health"], summary="Service health check")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------
from fastapi import WebSocket
from app.services.websocket_service import manager

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect messages from client for now, just keep connection open
            await websocket.receive_text()
    except Exception:
        manager.disconnect(websocket)
