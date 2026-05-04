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
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/upload", summary="Clone a remote Git repository locally")
def upload_repo(body: CloneRequest):
    """Clone the given Git URL into the local `repo/` directory."""
    try:
        path = clone_repo(body.repo_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"message": f"Repository cloned to {path}", "repo_path": path}


@router.post("/index", summary="Embed and store a local codebase in ChromaDB")
def index_repo(body: IndexRequest):
    """
    Walk *repo_path*, chunk every supported source file at function/class
    granularity, embed with the Jina v2 code model, and persist to Chroma.

    Returns the stable `repo_id` needed by all other endpoints.
    """
    try:
        _, repo_id = process_and_store_codebase(body.repo_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {
        "message": "Codebase indexed successfully.",
        "repo_id": repo_id,
        "repo_path": body.repo_path,
    }


@router.post("/clone-and-index", summary="Clone a remote repo then immediately index it")
def clone_and_index(body: CloneAndIndexRequest):
    """
    Convenience endpoint: clones the repo then runs the full embedding pipeline
    in one call.  Returns both the local path and the `repo_id`.
    """
    try:
        repo_path = clone_repo(body.repo_url)
        _, repo_id = process_and_store_codebase(repo_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {
        "message": "Repository cloned and indexed successfully.",
        "repo_path": repo_path,
        "repo_id": repo_id,
    }


@router.post("/diff-pipeline", summary="Run diff-driven test-prompt generation")
def diff_pipeline(body: DiffPipelineRequest):
    """
    Compares HEAD vs HEAD~1 for *repo_path*, retrieves related code/test chunks
    from the vector store, and returns LLM-ready test-update prompts — one per
    changed hunk.

    Pass either `repo_id` (to reuse an existing Chroma collection) or omit it
    if the vectorstore is already loaded in-process.
    """
    try:
        results = run_diff_pipeline(
            repo_path=body.repo_path,
            repo_id=body.repo_id,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"prompt_count": len(results), "results": results}


@router.post("/update", summary="Incrementally re-embed files changed in the last commit")
def update_repo(body: UpdateRequest):
    """
    Re-indexes only the files that changed in the most recent git commit,
    making incremental updates much faster than a full re-index.
    """
    try:
        _, total_added = update_vectorstore(
            repo_path=body.repo_path,
            repo_id=body.repo_id,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {
        "message": "Incremental update complete.",
        "chunks_added_or_updated": total_added,
    }


@router.post("/query", summary="Semantic search over an indexed codebase")
def query_repo(body: QueryRequest):
    """
    Run a similarity search against the Chroma collection for *repo_id*.
    Returns the top-k implementation chunks and top-k test chunks most
    relevant to *query*.
    """
    try:
        vs = load_vectorstore(body.repo_id)
        code_docs, test_docs = retrieve_related_chunks(
            query=body.query,
            vectorstore=vs,
            k_code=body.k_code,
            k_tests=body.k_tests,
            meta_language_if_known=body.language,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
    """Returns the deterministic `repo_id` for a given local repository path."""
    return {"repo_path": repo_path, "repo_id": make_repo_id(repo_path)}