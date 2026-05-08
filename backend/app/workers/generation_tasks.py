"""Celery tasks for AI test generation workflows."""

import logging

from app.orchestrators.test_generation_orchestrator import run_pipeline
from app.services.repo_service import clone_repo
from app.services.vectorstore_service import make_repo_id
from app.workers.celery_app import celery_app


logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.trigger_generation_job")
def trigger_generation_job(repo_url: str, commit_sha: str | None = None) -> dict:
    logger.info("[generation_task] start repo_url=%s commit=%s", repo_url, commit_sha)

    repo_path = clone_repo(repo_url)
    repo_id = make_repo_id(repo_path)
    result = run_pipeline(repo_path=repo_path, repo_id=repo_id, pull=True)

    logger.info("[generation_task] completed repo_id=%s status=%s", repo_id, result.status)
    return {
        "repo_id": repo_id,
        "status": result.status,
        "total_prompts": result.total_hunks,
        "generated_tests": result.generated_tests,
    }


@celery_app.task(name="tasks.trigger_diff_job")
def trigger_diff_job(repo_url: str, commit_sha: str | None = None) -> dict:
    """Run the diff pipeline to generate prompt artifacts without writing tests."""

    logger.info("[diff_task] start repo_url=%s commit=%s", repo_url, commit_sha)
    repo_path = clone_repo(repo_url)
    repo_id = make_repo_id(repo_path)
    results = run_diff_pipeline(repo_path=repo_path, repo_id=repo_id)
    logger.info("[diff_task] completed repo_id=%s prompts=%d", repo_id, len(results))
    return {"repo_id": repo_id, "prompt_count": len(results)}
