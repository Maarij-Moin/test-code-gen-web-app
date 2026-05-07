"""FastAPI routes for AI-driven test generation workflows."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.core.auth import api_key_dependency
from app.schemas.diff_schema import (
    DiffPipelineRequest,
    DiffPipelineResponse,
    UpdateVectorstoreRequest,
    UpdateVectorstoreResponse,
)
from app.schemas.query_schema import QueryRequest, QueryResponse, QueryResult
from app.services.test_services import (
    format_test_generation_response,
    generate_test_prompts,
    query_test_chunks,
    summarize_generated_tests,
    trigger_incremental_update,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tests", tags=["tests"], dependencies=[api_key_dependency])


def _http_error(exc: Exception, endpoint: str) -> HTTPException:
    """Map service-layer exceptions to HTTP responses."""

    detail = str(exc)
    if isinstance(exc, (ValueError, TypeError)):
        logger.warning("[%s] Bad request: %s", endpoint, detail)
        return HTTPException(status_code=422, detail=detail)
    if isinstance(exc, FileNotFoundError):
        logger.warning("[%s] Not found: %s", endpoint, detail)
        return HTTPException(status_code=404, detail=detail)
    if isinstance(exc, NotADirectoryError):
        logger.warning("[%s] Invalid repo path: %s", endpoint, detail)
        return HTTPException(status_code=400, detail=detail)
    logger.error("[%s] Unexpected error: %s", endpoint, detail, exc_info=True)
    return HTTPException(status_code=500, detail=detail)


@router.post("/generate", response_model=DiffPipelineResponse, summary="Generate AI test prompts")
def generate_tests(body: DiffPipelineRequest):
    """Generate test prompts for changed code using the diff pipeline."""

    logger.info(
        "[generate_tests] repo_path='%s' repo_id='%s'", body.repo_path, body.repo_id
    )
    try:
        results = generate_test_prompts(repo_path=body.repo_path, repo_id=body.repo_id)
        summary = summarize_generated_tests(results)
        logger.info("[generate_tests] Summary: %s", summary)
        return format_test_generation_response(results)
    except Exception as exc:
        raise _http_error(exc, "generate_tests")


@router.post("/update", response_model=UpdateVectorstoreResponse, summary="Update test vectorstore")
def update_tests(body: UpdateVectorstoreRequest):
    """Incrementally update vectorstore chunks based on the latest repo diff."""

    logger.info(
        "[update_tests] repo_path='%s' repo_id='%s'", body.repo_path, body.repo_id
    )
    try:
        updated_chunks = trigger_incremental_update(
            repo_path=body.repo_path,
            repo_id=body.repo_id,
        )
        return {"success": True, "updated_chunks": updated_chunks}
    except Exception as exc:
        raise _http_error(exc, "update_tests")


@router.post("/query-tests", response_model=QueryResponse, summary="Query test-only chunks")
def query_tests(body: QueryRequest):
    """Query only test-related chunks from the vectorstore."""

    logger.info(
        "[query_tests] repo_id='%s' query='%.80s' k=%d",
        body.repo_id,
        body.query,
        body.k,
    )
    try:
        test_chunks = query_test_chunks(repo_id=body.repo_id, query=body.query, k=body.k)
        results = [
            QueryResult(content=d.page_content, metadata=d.metadata, score=None)
            for d in test_chunks
        ]
        return {
            "success": True,
            "total_results": len(results),
            "results": results,
        }
    except Exception as exc:
        raise _http_error(exc, "query_tests")
