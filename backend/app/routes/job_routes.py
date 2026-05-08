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


class JobStep(BaseModel):
    name: str
    status: str
    duration_ms: int | None = None

class JobResponse(BaseModel):
    id: str
    repo_id: str
    repo_name: str
    type: str
    status: str
    progress: int
    started_at: str
    finished_at: str | None = None
    message: str | None = None
    steps: list[JobStep] = Field(default_factory=list)

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

def _job_to_response(job) -> JobResponse:
    """Map an IngestionJob ORM instance to the API response schema for frontend."""

    def _fmt(dt) -> str | None:
        return dt.isoformat() if dt else None

    # Map status to frontend status: queued | running | succeeded | failed | cancelled
    mapped_status = job.status.lower()
    if mapped_status in ("pending", "queued"):
        status_enum = "queued"
    elif mapped_status in ("cloning", "indexing", "running"):
        status_enum = "running"
    elif mapped_status in ("completed", "succeeded"):
        status_enum = "succeeded"
    elif mapped_status == "failed":
        status_enum = "failed"
    else:
        status_enum = "queued"
        
    # Calculate progress heuristics based on legacy status
    progress = 0
    if status_enum == "succeeded":
        progress = 100
    elif mapped_status == "cloning":
        progress = 20
    elif mapped_status == "indexing":
        progress = 50

    steps = []
    if job.cloning_started_at:
        steps.append(JobStep(name="Clone Repository", status="succeeded" if mapped_status != "cloning" else "running"))
    if job.indexing_started_at:
        steps.append(JobStep(name="Index Codebase", status="succeeded" if mapped_status == "completed" else "running"))
        
    return JobResponse(
        id=str(job.id),
        repo_id=str(job.vector_repo_id or job.repo_url),
        repo_name=job.repo_name or job.repo_url.split("/")[-1].replace(".git", ""),
        type="index",
        status=status_enum,
        progress=progress,
        started_at=_fmt(job.started_at) or _fmt(job.created_at) or "",
        finished_at=_fmt(job.completed_at),
        message=job.detail or job.error_message,
        steps=steps,
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
    response_model=JobResponse,
    summary="Poll a single ingestion job",
    responses={
        200: {"description": "Job found — inspect `status` and `detail`."},
        404: {"description": "No job with that ID exists."},
    },
)
async def get_job_status(job_id: str) -> JobResponse:
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
    response_model=list[JobResponse],
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
) -> list[JobResponse]:
    """List all ingestion jobs, optionally filtered by status."""
    jobs = await list_jobs(status=status, limit=limit, offset=offset)
    return [_job_to_response(j) for j in jobs]
