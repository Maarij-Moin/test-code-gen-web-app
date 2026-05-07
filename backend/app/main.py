import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.logging_config import setup_logging
from app.routes.repo_routes import router as repo_router

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
    allow_origins=["*"],
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

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(repo_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["health"], summary="Service health check")
def health():
    """Returns 200 OK when the service is running."""
    return {"status": "ok"}