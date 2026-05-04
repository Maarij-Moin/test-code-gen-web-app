import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.repo_routes import router as repo_router

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan: runs on startup / shutdown
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