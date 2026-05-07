"""Repository API routes — synchronous operations + async clone-and-index.

The ``/clone-and-index`` endpoint has been upgraded to a **non-blocking** async
job dispatcher.  It returns HTTP 202 with a ``job_id`` immediately; the actual
clone + index pipeline runs in a FastAPI BackgroundTask.

All other endpoints (upload, index, diff-pipeline, update, query, repo-id)
remain synchronous and unchanged.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.repo_service import clone_repo
from app.services.embedding_service import (
    make_repo_id,
    process_and_store_codebase,
    load_vectorstore,
    run_diff_pipeline,
    update_vectorstore,
    retrieve_related_chunks,
)
from app.services.job_service import create_job
from app.services.repo_worker import run_ingestion_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repos", tags=["repos"])


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class CloneRequest(BaseModel):
    repo_url: str


class IndexRequest(BaseModel):
    repo_path: str


class CloneAndIndexRequest(BaseModel):
    """Payload for the async clone-and-index endpoint."""

    repo_url: str = Field(
        ...,
        min_length=5,
        description="Git repository URL to clone and index asynchronously.",
        examples=["https://github.com/org/project.git"],
    )


class DiffPipelineRequest(BaseModel):
    repo_path: str
    repo_id: str | None = None


class UpdateRequest(BaseModel):
    repo_path: str
    repo_id: str


class QueryRequest(BaseModel):
    repo_id: str
    query: str
    k_code: int = 5
    k_tests: int = 3
    language: str | None = None


# ---------------------------------------------------------------------------
# Error helper
# ---------------------------------------------------------------------------

def _http_error(exc: Exception, endpoint: str) -> HTTPException:
    detail = str(exc)
    if isinstance(exc, (ValueError, TypeError)):
        logger.warning("[%s] Bad request: %s", endpoint, detail)
        return HTTPException(status_code=422, detail=detail)
    if isinstance(exc, FileNotFoundError):
        logger.warning("[%s] Not found: %s", endpoint, detail)
        return HTTPException(status_code=404, detail=detail)
    if isinstance(exc, RuntimeError):
        logger.error("[%s] Upstream/runtime error: %s", endpoint, detail, exc_info=True)
        return HTTPException(status_code=502, detail=detail)
    logger.error("[%s] Unexpected error: %s", endpoint, detail, exc_info=True)
    return HTTPException(status_code=500, detail=detail)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload", summary="Clone a remote Git repository locally (synchronous)")
def upload_repo(body: CloneRequest):
    logger.info("[upload_repo] Cloning repo_url='%s'", body.repo_url)
    try:
        path = clone_repo(body.repo_url)
    except Exception as exc:
        raise _http_error(exc, "upload_repo")
    logger.info("[upload_repo] Success — repo_path='%s'", path)
    return {"message": f"Repository cloned to {path}", "repo_path": path}


@router.post("/index", summary="Embed and store a local codebase in ChromaDB (synchronous)")
def index_repo(body: IndexRequest):
    logger.info("[index_repo] Indexing repo_path='%s'", body.repo_path)
    try:
        _, repo_id = process_and_store_codebase(body.repo_path)
    except Exception as exc:
        raise _http_error(exc, "index_repo")
    logger.info("[index_repo] Success — repo_id='%s'", repo_id)
    return {
        "message": "Codebase indexed successfully.",
        "repo_id": repo_id,
        "repo_path": body.repo_path,
    }


@router.post(
    "/clone-and-index",
    status_code=202,
    summary="Async clone-and-index — returns job_id immediately",
    responses={
        202: {
            "description": (
                "Job accepted. Poll ``GET /jobs/{job_id}`` to follow progress. "
                "Terminal statuses: COMPLETED | FAILED."
            )
        },
        422: {"description": "Invalid repo_url."},
    },
)
async def clone_and_index(
    body: CloneAndIndexRequest,
    background_tasks: BackgroundTasks,
):
    """Submit a repository URL for **asynchronous** clone + index.

    The API returns **immediately** with HTTP 202 and a ``job_id``.
    The actual clone → embed → index pipeline runs in the background.

    Use ``GET /jobs/{job_id}`` to poll progress.  Once ``status`` is
    ``COMPLETED``, the ``vector_repo_id`` field contains the stable ID
    for semantic search queries.

    **Status lifecycle:**
    ```
    PENDING → CLONING → INDEXING → COMPLETED
                                 ↘ FAILED
    ```
    """
    logger.info("[clone_and_index] Async job submitted for repo_url='%s'", body.repo_url)

    # 1. Persist a PENDING job row — instantaneous.
    job = await create_job(body.repo_url)

    # 2. Schedule the pipeline; control returns to the caller immediately.
    background_tasks.add_task(run_ingestion_pipeline, job.id, body.repo_url)

    logger.info(
        "[clone_and_index] Job %s queued for repo_url='%s'", job.id, body.repo_url
    )
    return {
        "job_id": str(job.id),
        "status": "PENDING",
        "message": (
            f"Ingestion job accepted. "
            f"Poll GET /jobs/{job.id} for live status updates."
        ),
        "poll_url": f"/jobs/{job.id}",
    }


@router.post("/diff-pipeline", summary="Run diff-driven test-prompt generation")
def diff_pipeline(body: DiffPipelineRequest):
    logger.info(
        "[diff_pipeline] repo_path='%s'  repo_id=%s", body.repo_path, body.repo_id
    )
    try:
        results = run_diff_pipeline(
            repo_path=body.repo_path,
            repo_id=body.repo_id,
        )
    except Exception as exc:
        raise _http_error(exc, "diff_pipeline")
    logger.info("[diff_pipeline] Generated %d prompt(s).", len(results))
    return {"prompt_count": len(results), "results": results}


@router.post("/update", summary="Incrementally re-embed files changed in the last commit")
def update_repo(body: UpdateRequest):
    logger.info(
        "[update_repo] repo_path='%s'  repo_id='%s'", body.repo_path, body.repo_id
    )
    try:
        _, total_added = update_vectorstore(
            repo_path=body.repo_path,
            repo_id=body.repo_id,
        )
    except Exception as exc:
        raise _http_error(exc, "update_repo")
    logger.info("[update_repo] %d chunk(s) added/updated.", total_added)
    return {
        "message": "Incremental update complete.",
        "chunks_added_or_updated": total_added,
    }


@router.post("/query", summary="Semantic search over an indexed codebase")
def query_repo(body: QueryRequest):
    logger.info(
        "[query_repo] repo_id='%s'  query='%.80s'  k_code=%d  k_tests=%d",
        body.repo_id, body.query, body.k_code, body.k_tests,
    )
    try:
        vs = load_vectorstore(body.repo_id)
        code_docs, test_docs = retrieve_related_chunks(
            query=body.query,
            vectorstore=vs,
            k_code=body.k_code,
            k_tests=body.k_tests,
            meta_language_if_known=body.language,
        )
    except Exception as exc:
        raise _http_error(exc, "query_repo")
    logger.info(
        "[query_repo] Returning %d code chunk(s) and %d test chunk(s).",
        len(code_docs), len(test_docs),
    )
    return {
        "code_chunks": [
            {"content": d.page_content, "metadata": d.metadata} for d in code_docs
        ],
        "test_chunks": [
            {"content": d.page_content, "metadata": d.metadata} for d in test_docs
        ],
    }


@router.get("/repo-id", summary="Derive the stable repo_id for a local path")
def get_repo_id(repo_path: str = Query(..., description="Absolute path to the repo root")):
    return {"repo_path": repo_path, "repo_id": make_repo_id(repo_path)}
