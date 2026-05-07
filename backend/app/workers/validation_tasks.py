"""Celery tasks for test validation workflows."""

import logging

from app.workers.celery_app import celery_app


logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.trigger_validation_job")
def trigger_validation_job(repo_id: str) -> dict:
    logger.info("[validation_task] repo_id=%s", repo_id)
    return {"repo_id": repo_id, "status": "queued"}
