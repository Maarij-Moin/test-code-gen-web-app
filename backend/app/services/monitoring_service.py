import asyncio
import logging
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.models import Repository
from app.services.repo_service import clone_repo, pull_repo
from app.workers.generation_tasks import trigger_diff_job
import git

logger = logging.getLogger(__name__)

async def check_repos_for_updates():
    """Check all repositories for new commits."""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Repository))
            repos = result.scalars().all()
            
            for repo in repos:
                try:
                    repo_path = clone_repo(repo.repo_url)
                    pull_repo(repo_path)
                    
                    local_repo = git.Repo(repo_path)
                    latest_commit = local_repo.head.commit.hexsha
                    
                    # We can store the latest checked commit in the Repository model.
                    # Currently, the repository model has `last_indexed_at` but let's check
                    # if the latest job for this repo matches the latest commit.
                    from app.db.models import Job
                    
                    # Find if we already have a diff job for this commit
                    job_stmt = select(Job).where(
                        Job.repo_id == repo.id,
                        Job.job_type == "diff",
                        Job.commit_sha == latest_commit
                    )
                    job_result = await session.execute(job_stmt)
                    existing_job = job_result.scalar_one_or_none()
                    
                    if not existing_job:
                        logger.info(f"[monitoring] Detected new commit {latest_commit} for {repo.name}. Triggering diff pipeline.")
                        
                        # Create job
                        job = Job(
                            repo_id=repo.id,
                            job_type="diff",
                            status="queued",
                            commit_sha=latest_commit,
                            payload={"branch": repo.default_branch}
                        )
                        session.add(job)
                        await session.commit()
                        
                        # Trigger Celery
                        trigger_diff_job.delay(repo_url=repo.repo_url, commit_sha=latest_commit)
                except Exception as e:
                    logger.error(f"[monitoring] Failed to check repo {repo.name}: {e}")
    except Exception as e:
        logger.error(f"[monitoring] Error in monitor loop: {e}")

async def monitoring_loop():
    """Background loop to check repos every 30 seconds."""
    logger.info("[monitoring] Starting repository monitoring loop")
    while True:
        await check_repos_for_updates()
        await asyncio.sleep(30)
