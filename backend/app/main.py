import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.core.logging_config import setup_logging
from app.core.config import settings
from app.routes.auth_routes import router as auth_router
from app.routes.job_routes import router as job_router
from app.routes.webhook_routes import router as webhook_router      # production: push + PR + replay protection
from app.api.routes.repo_routes import router as repo_router
from app.api.routes.test_routes import router as test_router
from app.db.database import init_auth_db

# ---------------------------------------------------------------------------
# Logging — centralized config (console + rotating file handlers)
# ---------------------------------------------------------------------------
setup_logging()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan: startup / shutdown hooks
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Automated Test-Generation API starting up …")
    await init_auth_db()
    # Ensure the ingestion_jobs table exists (uses the same SQLite AuthBase).
    # No Alembic migration is needed — create_all is idempotent.
    from app.models.job_model import IngestionJob  # noqa: F401  (side-effect import)
    from app.models.user_model import AuthBase
    from app.db.database import engine
    async with engine.begin() as conn:
        await conn.run_sync(AuthBase.metadata.create_all)
    yield
    logger.info("Automated Test-Generation API shutting down …")


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
# CORS — allow all origins in development; tighten for production
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Global exception handler — catches anything that slipped through the
# route-level handlers and ensures a JSON error body is always returned.
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unhandled exceptions.

    Logs the full traceback at ERROR level (without leaking it to the caller)
    and returns a generic 500 JSON response.
    """
    logger.error(
        "Unhandled exception on %s %s: %s\n%s",
        request.method,
        request.url.path,
        exc,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected internal error occurred. Check server logs for details."
        },
    )


@app.exception_handler(OperationalError)
async def database_exception_handler(request: Request, exc: OperationalError) -> JSONResponse:
    logger.error(
        "Database connection failed on %s %s: %s",
        request.method,
        request.url.path,
        exc,
    )
    return JSONResponse(
        status_code=503,
        content={"detail": "Database is unavailable. Start PostgreSQL and run migrations."},
    )

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth_router)
app.include_router(job_router)      # GET/POST /jobs/*
app.include_router(webhook_router)  # POST /webhooks/github  GET /webhooks/health
app.include_router(repo_router)
app.include_router(test_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["health"], summary="Service health check")
def health():
    """Returns 200 OK when the service is running."""
    return {"status": "ok"}
