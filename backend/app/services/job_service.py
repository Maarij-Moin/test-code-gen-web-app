"""
Job Service — async CRUD operations for IngestionJob records.

All operations use the shared AsyncSessionLocal from the database module,
creating their own short-lived sessions to avoid sharing state across
background tasks.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal
from app.models.job_model import IngestionJob, JobStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(tz=timezone.utc)


async def _save(session: AsyncSession, job: IngestionJob) -> IngestionJob:
    """Merge, commit, and refresh a job record within an open session."""
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def create_job(repo_url: str) -> IngestionJob:
    """Persist a new PENDING ingestion job and return it.

    Args:
        repo_url: The Git repository URL submitted by the caller.

    Returns:
        The newly created, persisted IngestionJob instance.
    """
    job = IngestionJob(
        repo_url=repo_url,
        status=JobStatus.PENDING.value,
        detail="Job created; waiting for worker to pick up.",
        started_at=_utcnow(),
    )
    async with AsyncSessionLocal() as session:
        result = await _save(session, job)
        logger.info("[job_service] Created job id=%s for repo_url=%r", result.id, repo_url)
        return result


async def get_job(job_id: str) -> IngestionJob | None:
    """Fetch a single IngestionJob by primary key.

    Args:
        job_id: UUID string of the job to retrieve.

    Returns:
        The IngestionJob if found, otherwise None.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(IngestionJob).where(IngestionJob.id == job_id)
        )
        return result.scalar_one_or_none()


async def list_jobs(
    *,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[IngestionJob]:
    """List ingestion jobs with optional status filter and pagination.

    Args:
        status:  Optional status string to filter by (e.g. "PENDING").
        limit:   Maximum number of rows to return (default 50, max 200).
        offset:  Row offset for pagination.

    Returns:
        List of IngestionJob instances ordered by created_at descending.
    """
    stmt = select(IngestionJob).order_by(IngestionJob.created_at.desc())
    if status:
        stmt = stmt.where(IngestionJob.status == status)
    stmt = stmt.limit(min(limit, 200)).offset(offset)

    async with AsyncSessionLocal() as session:
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def transition_status(
    job_id: str,
    *,
    new_status: JobStatus,
    detail: str | None = None,
    extra: dict[str, Any] | None = None,
) -> IngestionJob | None:
    """Atomically update a job's status, detail, and optional extra fields.

    Timestamps are automatically applied for phase boundaries:
        - CLONING    → cloning_started_at
        - INDEXING   → indexing_started_at
        - COMPLETED  → completed_at
        - FAILED     → completed_at

    Args:
        job_id:     UUID string of the job to update.
        new_status: Target JobStatus enum value.
        detail:     Human-readable progress message to expose via the API.
        extra:      Optional dict of additional column values to patch
                    (e.g. {"local_path": "/repo/myproject"}).

    Returns:
        The updated IngestionJob, or None if not found.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(IngestionJob).where(IngestionJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        if job is None:
            logger.warning("[job_service] transition_status: job %s not found.", job_id)
            return None

        now = _utcnow()
        job.status = new_status.value
        if detail is not None:
            job.detail = detail
        job.updated_at = now

        # Auto-timestamp phase transitions
        if new_status == JobStatus.CLONING:
            job.cloning_started_at = now
        elif new_status == JobStatus.INDEXING:
            job.indexing_started_at = now
        elif new_status in (JobStatus.COMPLETED, JobStatus.FAILED):
            job.completed_at = now

        # Patch any extra fields supplied by the caller
        if extra:
            for field, value in extra.items():
                if hasattr(job, field):
                    setattr(job, field, value)
                else:
                    logger.warning(
                        "[job_service] transition_status: unknown field %r ignored.", field
                    )

        updated = await _save(session, job)
        logger.info(
            "[job_service] Job %s → %s | %s",
            job_id,
            new_status.value,
            detail or "",
        )
        return updated


async def mark_failed(
    job_id: str,
    *,
    error_message: str,
    detail: str | None = None,
) -> IngestionJob | None:
    """Convenience wrapper to move a job to FAILED with a full error message.

    Args:
        job_id:        UUID string of the job.
        error_message: Full exception text or structured error body.
        detail:        Short human-readable summary (defaults to error_message[:200]).

    Returns:
        The updated IngestionJob, or None if not found.
    """
    summary = detail or error_message[:200]
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(IngestionJob).where(IngestionJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        if job is None:
            logger.warning("[job_service] mark_failed: job %s not found.", job_id)
            return None

        job.status = JobStatus.FAILED.value
        job.error_message = error_message
        job.detail = summary
        job.completed_at = _utcnow()
        job.updated_at = _utcnow()

        updated = await _save(session, job)
        logger.error("[job_service] Job %s FAILED: %s", job_id, summary)
        return updated
