"""
Repo Worker — the async background pipeline that runs after a job is created.

Pipeline stages
---------------
1. CLONING   — clone the repo if it does not exist locally; ``git pull`` if it does.
2. INDEXING  — chunk every source file and embed into ChromaDB.
3. COMPLETED — update job with vector_repo_id and mark success.

On any unhandled exception the job is marked FAILED with the full traceback
captured in ``error_message`` so operators can inspect it later.

Timeout handling
----------------
Each phase is wrapped with ``asyncio.wait_for`` against configurable deadlines:
    - CLONE_TIMEOUT_SECONDS   (default 300 s, ~5 min)
    - INDEXING_TIMEOUT_SECONDS (default 1800 s, ~30 min)

Both are module-level constants you can override via environment variables.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import traceback
from concurrent.futures import ThreadPoolExecutor

from app.core.config import settings
from app.models.job_model import JobStatus
from app.services.job_service import mark_failed, transition_status
from app.services.repo_service import clone_repo, pull_repo
from app.services.indexing_service import process_and_store_codebase

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Timeouts (seconds)
# ---------------------------------------------------------------------------
CLONE_TIMEOUT_SECONDS: int = int(os.getenv("CLONE_TIMEOUT_SECONDS", "300"))
INDEXING_TIMEOUT_SECONDS: int = int(os.getenv("INDEXING_TIMEOUT_SECONDS", "1800"))

# A dedicated thread pool isolates CPU/IO-heavy blocking work from the event
# loop.  max_workers=2 prevents a thundering-herd of concurrent clone+index
# operations saturating disk/network.
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="repo-worker")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _run_in_thread(func, *args):
    """Run a synchronous callable in the shared worker thread pool.

    Args:
        func:  Synchronous function to call.
        *args: Positional arguments forwarded to func.

    Returns:
        Whatever func returns.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_EXECUTOR, func, *args)


def _clone_or_pull(repo_url: str, base_dir: str) -> str:
    """Synchronous helper: clone if not present, pull if already cloned.

    Args:
        repo_url:  Remote Git URL.
        base_dir:  Root directory for local repo storage.

    Returns:
        Local filesystem path to the repo root.

    Raises:
        RuntimeError: If clone or pull fails.
    """
    stripped = repo_url.strip().rstrip("/")
    repo_name = stripped.split("/")[-1].replace(".git", "")
    repo_path = os.path.join(base_dir, repo_name)

    if os.path.exists(os.path.join(repo_path, ".git")):
        logger.info("[repo_worker] Repo already cloned at %s — pulling latest.", repo_path)
        pull_repo(repo_path)
    else:
        logger.info("[repo_worker] Cloning %s → %s …", repo_url, repo_path)
        # clone_repo handles partial-clone cleanup on failure
        repo_path = clone_repo(repo_url)

    return repo_path


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def run_ingestion_pipeline(job_id: str, repo_url: str) -> None:
    """Drive the full async ingestion pipeline for a single job.

    This coroutine is designed to be scheduled via FastAPI BackgroundTasks or
    directly ``await``ed inside a Celery task wrapper.

    Lifecycle transitions emitted:
        PENDING → CLONING → INDEXING → COMPLETED
        Any stage → FAILED (on exception or timeout)

    Args:
        job_id:   UUID string of the IngestionJob created by the route.
        repo_url: Git remote URL to clone and index.
    """
    logger.info("[repo_worker] Pipeline start. job_id=%s repo_url=%r", job_id, repo_url)
    base_dir = settings.REPO_BASE_DIR

    # ------------------------------------------------------------------ #
    # Phase 1: CLONING                                                    #
    # ------------------------------------------------------------------ #
    await transition_status(
        job_id,
        new_status=JobStatus.CLONING,
        detail=f"Cloning repository from {repo_url} …",
    )

    try:
        repo_path: str = await asyncio.wait_for(
            _run_in_thread(_clone_or_pull, repo_url, base_dir),
            timeout=CLONE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        msg = (
            f"Cloning timed out after {CLONE_TIMEOUT_SECONDS}s. "
            "Repository may be too large or the network is slow."
        )
        logger.error("[repo_worker] %s job_id=%s", msg, job_id)
        await mark_failed(job_id, error_message=msg, detail="Clone timeout.")
        return
    except Exception as exc:  # noqa: BLE001
        full_tb = traceback.format_exc()
        logger.error(
            "[repo_worker] Clone failed. job_id=%s\n%s", job_id, full_tb
        )
        await mark_failed(
            job_id,
            error_message=full_tb,
            detail=f"Clone failed: {exc}",
        )
        return

    repo_name = os.path.basename(repo_path)
    logger.info("[repo_worker] Clone complete. repo_path=%s", repo_path)

    await transition_status(
        job_id,
        new_status=JobStatus.CLONING,      # still CLONING until indexing starts
        detail=f"Clone complete. Repo at {repo_path}. Preparing to index …",
        extra={"local_path": repo_path, "repo_name": repo_name},
    )

    # ------------------------------------------------------------------ #
    # Phase 2: INDEXING                                                   #
    # ------------------------------------------------------------------ #
    await transition_status(
        job_id,
        new_status=JobStatus.INDEXING,
        detail="Chunking and embedding codebase into ChromaDB …",
        extra={"local_path": repo_path, "repo_name": repo_name},
    )

    try:
        _, vector_repo_id = await asyncio.wait_for(
            _run_in_thread(process_and_store_codebase, repo_path),
            timeout=INDEXING_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        msg = (
            f"Indexing timed out after {INDEXING_TIMEOUT_SECONDS}s. "
            "The codebase may be too large; consider increasing INDEXING_TIMEOUT_SECONDS."
        )
        logger.error("[repo_worker] %s job_id=%s", msg, job_id)
        await mark_failed(job_id, error_message=msg, detail="Indexing timeout.")
        return
    except Exception as exc:  # noqa: BLE001
        full_tb = traceback.format_exc()
        logger.error(
            "[repo_worker] Indexing failed. job_id=%s\n%s", job_id, full_tb
        )
        await mark_failed(
            job_id,
            error_message=full_tb,
            detail=f"Indexing failed: {exc}",
        )
        return

    logger.info(
        "[repo_worker] Indexing complete. job_id=%s vector_repo_id=%s",
        job_id,
        vector_repo_id,
    )

    # ------------------------------------------------------------------ #
    # Phase 3: COMPLETED                                                  #
    # ------------------------------------------------------------------ #
    await transition_status(
        job_id,
        new_status=JobStatus.COMPLETED,
        detail=(
            f"Pipeline complete. Codebase indexed as vector_repo_id='{vector_repo_id}'."
        ),
        extra={
            "vector_repo_id": vector_repo_id,
            "local_path": repo_path,
            "repo_name": repo_name,
        },
    )

    logger.info(
        "[repo_worker] Pipeline finished successfully. job_id=%s vector_repo_id=%s",
        job_id,
        vector_repo_id,
    )
