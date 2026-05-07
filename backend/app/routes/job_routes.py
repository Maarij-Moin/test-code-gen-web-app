"""
Job Routes — REST endpoints for submitting and polling async ingestion jobs.

Endpoints
---------
POST /jobs/ingest        Submit a repo URL and receive a job_id immediately.
GET  /jobs/{job_id}      Poll a single job's status.
GET  /jobs               List all jobs (filterable by status, paginated).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.models.job_model import JobStatus
from app.services.job_service import create_job, get_job, list_jobs
from app.services.repo_worker import run_ingestion_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class IngestRequest(BaseModel):
    """Payload for the async clone-and-index endpoint."""

    repo_url: str = Field(
        ...,
        min_length=5,
        description="Git repository URL to clone and index.",
        examples=["https://github.com/org/project.git"],
    )

    @field_validator("repo_url")
    @classmethod
    def _validate_url(cls, v: str) -> str:
        v = v.strip()
        if not (
            v.startswith("https://")
            or v.startswith("http://")
            or v.startswith("git@")
            or v.startswith("ssh://")
        ):
            raise ValueError(
                "repo_url must start with https://, http://, git@, or ssh://."
            )
        return v

    class Config:
        json_schema_extra = {
            "example": {"repo_url": "https://github.com/org/project.git"}
        }


class JobStatusResponse(BaseModel):
    """API representation of an IngestionJob."""

    job_id: str = Field(..., description="Unique job identifier (UUID).")
    repo_url: str
    repo_name: str | None = None
    local_path: str | None = None
    vector_repo_id: str | None = None
    status: str = Field(..., description="One of PENDING | CLONING | INDEXING | COMPLETED | FAILED.")
    detail: str | None = Field(None, description="Human-readable progress message.")
    error_message: str | None = Field(None, description="Full error text when status=FAILED.")
    created_at: str | None = None
    started_at: str | None = None
    cloning_started_at: str | None = None
    indexing_started_at: str | None = None
    completed_at: str | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "3d6f4e1a-...",
                "repo_url": "https://github.com/org/project.git",
                "status": "INDEXING",
                "detail": "Chunking and embedding codebase into ChromaDB …",
            }
        }


class IngestResponse(BaseModel):
    """Immediate response returned when a job is accepted."""

    job_id: str = Field(..., description="Poll this ID against GET /jobs/{job_id}.")
    status: str = JobStatus.PENDING.value
    message: str = "Ingestion job accepted. Poll /jobs/{job_id} for progress."

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "3d6f4e1a-...",
                "status": "PENDING",
                "message": "Ingestion job accepted. Poll /jobs/{job_id} for progress.",
            }
        }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _job_to_response(job) -> JobStatusResponse:
    """Map an IngestionJob ORM instance to the API response schema."""

    def _fmt(dt) -> str | None:
        return dt.isoformat() if dt else None

    return JobStatusResponse(
        job_id=str(job.id),
        repo_url=job.repo_url,
        repo_name=job.repo_name,
        local_path=job.local_path,
        vector_repo_id=job.vector_repo_id,
        status=job.status,
        detail=job.detail,
        error_message=job.error_message,
        created_at=_fmt(job.created_at),
        started_at=_fmt(job.started_at),
        cloning_started_at=_fmt(job.cloning_started_at),
        indexing_started_at=_fmt(job.indexing_started_at),
        completed_at=_fmt(job.completed_at),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=202,
    summary="Submit a repo URL for async clone-and-index",
    responses={
        202: {"description": "Job accepted; returns job_id for polling."},
        422: {"description": "Invalid repo URL."},
    },
)
async def submit_ingestion_job(
    body: IngestRequest,
    background_tasks: BackgroundTasks,
) -> IngestResponse:
    """Submit a repository URL for async ingestion.

    Returns immediately with a ``job_id``. The clone → index pipeline runs
    in a FastAPI background task.  Poll ``GET /jobs/{job_id}`` to follow
    progress.

    **Polling guidance**
    - Recommended interval: every 3–5 seconds.
    - Terminal statuses: ``COMPLETED`` or ``FAILED``.
    """
    logger.info("[job_routes] /ingest received repo_url=%r", body.repo_url)

    # 1. Persist a PENDING job row — this is instantaneous.
    job = await create_job(body.repo_url)

    # 2. Enqueue the pipeline as a non-blocking background task.
    background_tasks.add_task(run_ingestion_pipeline, job.id, body.repo_url)

    logger.info(
        "[job_routes] Job %s queued for repo_url=%r", job.id, body.repo_url
    )
    return IngestResponse(
        job_id=str(job.id),
        message=f"Ingestion job accepted. Poll /jobs/{job.id} for progress.",
    )


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Poll a single ingestion job",
    responses={
        200: {"description": "Job found — inspect `status` and `detail`."},
        404: {"description": "No job with that ID exists."},
    },
)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """Return the current status of an ingestion job.

    Poll this endpoint every few seconds until ``status`` is one of:
    ``COMPLETED`` or ``FAILED``.

    Once ``COMPLETED``, use ``vector_repo_id`` to query the indexed codebase.
    """
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return _job_to_response(job)


@router.get(
    "",
    response_model=list[JobStatusResponse],
    summary="List ingestion jobs",
    responses={
        200: {"description": "Paginated list of ingestion jobs."},
    },
)
async def list_ingestion_jobs(
    status: str | None = Query(
        default=None,
        description=(
            "Optional filter by status: PENDING | CLONING | INDEXING | COMPLETED | FAILED"
        ),
    ),
    limit: int = Query(default=20, ge=1, le=200, description="Max rows to return."),
    offset: int = Query(default=0, ge=0, description="Row offset for pagination."),
) -> list[JobStatusResponse]:
    """List all ingestion jobs, optionally filtered by status."""
    jobs = await list_jobs(status=status, limit=limit, offset=offset)
    return [_job_to_response(j) for j in jobs]
