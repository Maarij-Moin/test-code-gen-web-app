"""GitHub webhook processing service.

Flow:
1. Verify signature.
2. Parse push event payload.
3. Pull latest repo changes.
4. Track jobs in database.
5. Trigger indexing + diff + test generation tasks.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Job, Repository
from app.services.repo_service import clone_repo, pull_repo
from app.workers.generation_tasks import trigger_diff_job, trigger_generation_job
from app.workers.indexing_tasks import trigger_indexing_job


logger = logging.getLogger(__name__)


def verify_github_signature(body: bytes, signature: str | None) -> bool:
    """Validate GitHub webhook signature using sha256 HMAC."""

    if not settings.GITHUB_WEBHOOK_SECRET:
        return True
    if not signature:
        return False
    digest = hmac.new(settings.GITHUB_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    expected = f"sha256={digest}"
    return hmac.compare_digest(expected, signature)


def parse_push_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract repository + commit metadata from a GitHub push event."""

    repo = payload.get("repository") or {}
    ref = payload.get("ref") or ""
    branch = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ref
    commit_sha = payload.get("after")
    repo_url = repo.get("clone_url") or repo.get("html_url") or ""
    repo_name = repo.get("name") or ""
    default_branch = repo.get("default_branch") or "main"

    changed_files: list[str] = []
    for commit in payload.get("commits") or []:
        for key in ("added", "modified", "removed"):
            changed_files.extend(commit.get(key, []))

    return {
        "repo_url": repo_url,
        "repo_name": repo_name,
        "default_branch": default_branch,
        "branch": branch,
        "commit_sha": commit_sha,
        "changed_files": sorted(set(changed_files)),
    }


async def _get_or_create_repo(session: AsyncSession, repo_url: str, name: str, branch: str) -> Repository:
    result = await session.execute(select(Repository).where(Repository.repo_url == repo_url))
    repo = result.scalar_one_or_none()
    if repo:
        return repo

    repo = Repository(name=name or repo_url.split("/")[-1], repo_url=repo_url, default_branch=branch)
    session.add(repo)
    await session.commit()
    await session.refresh(repo)
    return repo


async def _job_exists(session: AsyncSession, repo_id, job_type: str, commit_sha: str | None) -> bool:
    stmt = select(Job).where(
        Job.repo_id == repo_id,
        Job.job_type == job_type,
        Job.commit_sha == commit_sha,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def _create_job(
    session: AsyncSession,
    repo_id,
    job_type: str,
    commit_sha: str | None,
    payload: dict[str, Any],
) -> Job:
    job = Job(repo_id=repo_id, job_type=job_type, status="queued", commit_sha=commit_sha, payload=payload)
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def handle_github_webhook(
    session: AsyncSession,
    payload_bytes: bytes,
    signature: str | None,
    event: str | None,
) -> dict[str, Any]:
    """Process a GitHub webhook payload and trigger background tasks."""

    logger.info("[webhook] received event=%s", event)

    if not verify_github_signature(payload_bytes, signature):
        raise ValueError("Invalid webhook signature")

    payload = json.loads(payload_bytes.decode("utf-8") or "{}")
    if event != "push":
        return {"status": "ignored", "event": event}

    data = parse_push_event(payload)
    if not data["repo_url"]:
        return {"status": "ignored", "reason": "missing repo URL"}

    repo = await _get_or_create_repo(session, data["repo_url"], data["repo_name"], data["branch"])

    # Ensure local clone exists and pull latest changes before tasks run.
    repo_path = clone_repo(data["repo_url"])
    pull_repo(repo_path)

    payload_meta = {
        "branch": data["branch"],
        "changed_files": data["changed_files"],
    }

    # Retry-safe: skip jobs that already exist for this commit.
    if not await _job_exists(session, repo.id, "indexing", data["commit_sha"]):
        await _create_job(session, repo.id, "indexing", data["commit_sha"], payload_meta)
        logger.info("[webhook] indexing started repo=%s", data["repo_url"])
        trigger_indexing_job.delay(repo_url=data["repo_url"], commit_sha=data["commit_sha"])

    if not await _job_exists(session, repo.id, "diff", data["commit_sha"]):
        await _create_job(session, repo.id, "diff", data["commit_sha"], payload_meta)
        logger.info("[webhook] diff pipeline started repo=%s", data["repo_url"])
        trigger_diff_job.delay(repo_url=data["repo_url"], commit_sha=data["commit_sha"])

    if not await _job_exists(session, repo.id, "generation", data["commit_sha"]):
        await _create_job(session, repo.id, "generation", data["commit_sha"], payload_meta)
        logger.info("[webhook] generation started repo=%s", data["repo_url"])
        trigger_generation_job.delay(repo_url=data["repo_url"], commit_sha=data["commit_sha"])

    logger.info("[webhook] generation enqueued repo=%s commit=%s", data["repo_url"], data["commit_sha"])

    return {
        "status": "accepted",
        "repo_url": data["repo_url"],
        "commit_sha": data["commit_sha"],
        "changed_files": data["changed_files"],
    }
