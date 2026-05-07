"""Celery tasks for repository indexing workflows."""

import logging

from app.core.config import settings
from app.services.repo_service import clone_repo
from app.services.indexing_service import process_and_store_codebase, update_vectorstore
from app.services.vectorstore_service import make_repo_id
from app.workers.celery_app import celery_app


logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.trigger_indexing_job")
def trigger_indexing_job(repo_url: str, commit_sha: str | None = None) -> dict:
    logger.info("[indexing_task] start repo_url=%s commit=%s", repo_url, commit_sha)

    repo_path = clone_repo(repo_url)
    repo_id = make_repo_id(repo_path)

    try:
        _, chunks = update_vectorstore(repo_path=repo_path, repo_id=repo_id)
        logger.info("[indexing_task] completed repo_id=%s chunks=%d", repo_id, chunks)
        return {"repo_id": repo_id, "updated_chunks": chunks}
    except Exception:
        _, repo_id = process_and_store_codebase(repo_path)
        logger.info("[indexing_task] full index repo_id=%s", repo_id)
        return {"repo_id": repo_id, "updated_chunks": 0}
