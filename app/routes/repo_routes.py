import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.repo_service import clone_repo
from app.services.embedding_service import (
    make_repo_id,
    process_and_store_codebase,
    load_vectorstore,
    run_diff_pipeline,
    update_vectorstore,
    retrieve_related_chunks,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repos", tags=["repos"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CloneRequest(BaseModel):
    repo_url: str

class IndexRequest(BaseModel):
    repo_path: str

class CloneAndIndexRequest(BaseModel):
    repo_url: str

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
# Helpers
# ---------------------------------------------------------------------------

def _http_error(exc: Exception, endpoint: str) -> HTTPException:
    """Map service-layer exceptions to appropriate HTTP status codes.

    Convention:
        ValueError / TypeError     → 422 Unprocessable Entity  (bad input)
        FileNotFoundError          → 404 Not Found             (repo / DB missing)
        RuntimeError               → 502 Bad Gateway           (git failure, network)
        Everything else            → 500 Internal Server Error
    """
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

@router.post("/upload", summary="Clone a remote Git repository locally")
def upload_repo(body: CloneRequest):
    """Clone the given Git URL into the local ``repo/`` directory."""
    logger.info("[upload_repo] Cloning repo_url='%s'", body.repo_url)
    try:
        path = clone_repo(body.repo_url)
    except Exception as exc:
        raise _http_error(exc, "upload_repo")
    logger.info("[upload_repo] Success — repo_path='%s'", path)
    return {"message": f"Repository cloned to {path}", "repo_path": path}


@router.post("/index", summary="Embed and store a local codebase in ChromaDB")
def index_repo(body: IndexRequest):
    """Walk *repo_path*, chunk every supported source file at function/class
    granularity, embed with the BGE model, and persist to Chroma.

    Returns the stable ``repo_id`` needed by all other endpoints.
    """
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


@router.post("/clone-and-index", summary="Clone a remote repo then immediately index it")
def clone_and_index(body: CloneAndIndexRequest):
    """Convenience endpoint: clones the repo then runs the full embedding
    pipeline in one call.  Returns both the local path and the ``repo_id``.
    """
    logger.info("[clone_and_index] repo_url='%s'", body.repo_url)
    try:
        repo_path = clone_repo(body.repo_url)
        _, repo_id = process_and_store_codebase(repo_path)
    except Exception as exc:
        raise _http_error(exc, "clone_and_index")
    logger.info(
        "[clone_and_index] Success — repo_path='%s'  repo_id='%s'", repo_path, repo_id
    )
    return {
        "message": "Repository cloned and indexed successfully.",
        "repo_path": repo_path,
        "repo_id": repo_id,
    }


@router.post("/diff-pipeline", summary="Run diff-driven test-prompt generation")
def diff_pipeline(body: DiffPipelineRequest):
    """Compare HEAD vs HEAD~1 for *repo_path*, retrieve related code/test chunks
    from the vector store, and return LLM-ready test-update prompts — one per
    changed hunk.

    Pass either ``repo_id`` (to reuse an existing Chroma collection) or omit it
    if the vectorstore is already loaded in-process.

    Raises **422** when:
    - The diff is empty (no commits / no changes).
    - No supported source files exist in the diff.

    Raises **404** when the ``repo_id`` Chroma collection does not exist.

    Raises **502** when the underlying ``git`` command fails (e.g. bad repo path,
    no HEAD~1).
    """
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
    """Re-index only the files that changed in the most recent git commit,
    making incremental updates much faster than a full re-index.
    """
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
    """Run a similarity search against the Chroma collection for *repo_id*.
    Returns the top-k implementation chunks and top-k test chunks most
    relevant to *query*.
    """
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
    """Returns the deterministic ``repo_id`` for a given local repository path."""
    return {"repo_path": repo_path, "repo_id": make_repo_id(repo_path)}