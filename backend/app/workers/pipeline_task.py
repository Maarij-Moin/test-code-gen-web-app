"""
Celery task: run the full autonomous test-generation pipeline.

This task is the production entry-point that ties together the ingestion
(clone + index) step from ``indexing_tasks`` with the orchestrator pipeline.

Trigger from anywhere in the codebase::

    from app.workers.pipeline_task import run_test_pipeline_task
    run_test_pipeline_task.delay(repo_url="https://github.com/org/repo.git")

Or from a webhook handler (after a push event is detected)::

    run_test_pipeline_task.apply_async(
        kwargs={
            "repo_url": repo_url,
            "commit_sha": commit_sha,
        },
        countdown=5,   # Small delay to ensure the push is fully processed.
    )
"""

from __future__ import annotations

import logging

from app.core.config import settings
from app.services.repo_service import clone_repo
from app.services.indexing_service import process_and_store_codebase, update_vectorstore
from app.services.vectorstore_service import make_repo_id
from app.orchestrators.test_generation_orchestrator import run_pipeline, PipelineResult
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="tasks.run_test_pipeline",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
)
def run_test_pipeline_task(
    self,
    repo_url: str,
    commit_sha: str | None = None,
    pull: bool = True,
    max_repair_attempts: int = 3,
) -> dict:
    """Celery task: clone/update → re-embed → run autonomous QA pipeline.

    This is a long-running task (potentially 10–30 minutes for large repos).
    It is designed to be run by a dedicated Celery worker with concurrency=1
    or a separate queue to avoid starving other tasks.

    Args:
        repo_url:             Git remote URL.
        commit_sha:           Optional HEAD commit SHA (for audit logging).
        pull:                 Whether to ``git pull`` before diffing.
        max_repair_attempts:  Maximum validation → repair cycles.

    Returns:
        Serialisable dict representation of the ``PipelineResult``.
    """
    logger.info(
        "[pipeline_task] Starting. repo_url=%s commit=%s",
        repo_url, commit_sha,
    )

    # ------------------------------------------------------------------ #
    # Step 1: Clone or pull the repository                                #
    # ------------------------------------------------------------------ #
    try:
        repo_path = clone_repo(repo_url)
    except Exception as exc:
        logger.exception("[pipeline_task] Clone failed: %s", exc)
        raise self.retry(exc=exc)

    repo_id = make_repo_id(repo_path)

    # ------------------------------------------------------------------ #
    # Step 2: Update (or create) the vectorstore                          #
    # ------------------------------------------------------------------ #
    try:
        _, chunks = update_vectorstore(repo_path=repo_path, repo_id=repo_id)
        logger.info("[pipeline_task] Vectorstore updated. chunks=%d", chunks)
    except Exception:
        # Fallback: full re-index if incremental update fails.
        logger.warning("[pipeline_task] Incremental update failed — running full index.")
        try:
            _, repo_id = process_and_store_codebase(repo_path)
            logger.info("[pipeline_task] Full index complete. repo_id=%s", repo_id)
        except Exception as exc:
            logger.exception("[pipeline_task] Full index also failed: %s", exc)
            raise self.retry(exc=exc)

    # ------------------------------------------------------------------ #
    # Step 3: Run the autonomous pipeline                                 #
    # ------------------------------------------------------------------ #
    result: PipelineResult = run_pipeline(
        repo_path=repo_path,
        repo_id=repo_id,
        pull=pull,
        max_repair_attempts=max_repair_attempts,
    )

    logger.info(
        "[pipeline_task] Pipeline finished. status=%s generated=%d validation=%s",
        result.status, result.generated_tests, result.validation_status,
    )

    # Return a JSON-serialisable summary (Celery result backend stores this).
    return {
        "repo_path": result.repo_path,
        "repo_id": result.repo_id,
        "commit_sha": result.commit_sha,
        "status": result.status,
        "total_hunks": result.total_hunks,
        "generated_tests": result.generated_tests,
        "validation_status": result.validation_status,
        "repair_attempts": result.repair_attempts,
        "pr_title": result.pr_title,
        "error": result.error,
        "audit_entries": len(result.audit_log),
    }
