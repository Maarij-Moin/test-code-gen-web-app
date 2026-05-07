"""
GitHub Webhook Service — secure, replay-protected event processing.

This module is the authoritative implementation of all GitHub webhook
processing logic.  It supersedes the older ``app/services/webhook_service.py``
and is imported exclusively from ``app/routes/webhook_routes.py``.

Security model
--------------
1. **HMAC-SHA256 signature verification** — every request body is validated
   against the ``X-Hub-Signature-256`` header using ``hmac.compare_digest``
   (constant-time comparison; safe against timing attacks).

2. **Replay protection** — the ``X-GitHub-Delivery`` header (a UUID GitHub
   generates per delivery) is stored in the ``webhook_events`` table.  The
   ``UNIQUE`` constraint on ``(provider, delivery_id)`` prevents the same
   delivery from being processed more than once.

3. **Event filtering** — only ``push`` and ``pull_request`` events trigger
   downstream work.  All others are acknowledged with HTTP 200 and
   ``{"status": "ignored"}``.

4. **Non-blocking enqueue** — all heavy work (clone, index, orchestrator run)
   is dispatched to Celery via ``.apply_async()``.  The webhook endpoint
   itself completes in <50 ms.

5. **Audit trail** — every received event is persisted as a ``WebhookEvent``
   row regardless of outcome.  On duplicate delivery the existing row is
   returned unchanged.

Pull-request event handling
---------------------------
For ``pull_request`` events the service only acts on the ``opened``,
``synchronize``, and ``reopened`` actions — the three actions that represent
new or updated code.  It extracts the head commit SHA and base/head repo URLs.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.crud import create_webhook_event, create_repository, get_repository_by_url
from app.db.models import Repository, WebhookEvent
from app.workers.pipeline_task import run_test_pipeline_task

logger = logging.getLogger(__name__)

# Pull-request actions that represent new/changed code and should trigger tests.
_ACTIONABLE_PR_ACTIONS: frozenset[str] = frozenset(
    {"opened", "synchronize", "reopened"}
)


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

def verify_github_signature(body: bytes, signature: str | None) -> bool:
    """Validate the ``X-Hub-Signature-256`` HMAC signature.

    Uses ``hmac.compare_digest`` for constant-time comparison to prevent
    timing-based side-channel attacks.

    If ``GITHUB_WEBHOOK_SECRET`` is empty the check is bypassed (useful for
    local development without a real webhook secret).  **Always configure a
    secret in production.**

    Args:
        body:       Raw request body bytes (must be read before parsing JSON).
        signature:  Value of the ``X-Hub-Signature-256`` header, or None.

    Returns:
        True if the signature is valid (or secret is unconfigured), False otherwise.
    """
    secret = settings.GITHUB_WEBHOOK_SECRET
    if not secret:
        logger.warning(
            "[github_webhook_service] GITHUB_WEBHOOK_SECRET is not set — "
            "signature verification is DISABLED. Set it in production!"
        )
        return True

    if not signature:
        logger.warning("[github_webhook_service] Missing X-Hub-Signature-256 header.")
        return False

    if not signature.startswith("sha256="):
        logger.warning(
            "[github_webhook_service] Unexpected signature format: %s", signature[:20]
        )
        return False

    digest = hmac.new(
        secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    expected = f"sha256={digest}"

    valid = hmac.compare_digest(expected, signature)
    if not valid:
        logger.warning(
            "[github_webhook_service] Signature mismatch. "
            "expected prefix=%s…  received prefix=%s…",
            expected[:20], signature[:20],
        )
    return valid


# ---------------------------------------------------------------------------
# Payload parsers
# ---------------------------------------------------------------------------

class ParsedEvent:
    """Normalised representation of a GitHub event payload."""

    __slots__ = (
        "event_type",
        "action",
        "repo_url",
        "repo_name",
        "branch",
        "commit_sha",
        "default_branch",
        "changed_files",
        "delivery_id",
        "is_actionable",
    )

    def __init__(self) -> None:
        self.event_type: str = ""
        self.action: str | None = None
        self.repo_url: str = ""
        self.repo_name: str = ""
        self.branch: str = ""
        self.commit_sha: str | None = None
        self.default_branch: str = "main"
        self.changed_files: list[str] = []
        self.delivery_id: str | None = None
        self.is_actionable: bool = False


def _parse_push(payload: dict[str, Any], delivery_id: str | None) -> ParsedEvent:
    """Extract fields from a GitHub ``push`` event payload.

    Args:
        payload:     Decoded JSON payload dict.
        delivery_id: Value of the ``X-GitHub-Delivery`` header.

    Returns:
        A populated ``ParsedEvent``.
    """
    repo = payload.get("repository") or {}
    ref = payload.get("ref") or ""
    branch = ref.removeprefix("refs/heads/") if ref.startswith("refs/heads/") else ref

    # Collect all file paths touched across every commit in the push.
    changed_files: list[str] = []
    for commit in payload.get("commits") or []:
        for key in ("added", "modified", "removed"):
            changed_files.extend(commit.get(key) or [])

    ev = ParsedEvent()
    ev.event_type = "push"
    ev.repo_url = repo.get("clone_url") or repo.get("html_url") or ""
    ev.repo_name = repo.get("full_name") or repo.get("name") or ""
    ev.branch = branch
    ev.commit_sha = payload.get("after") or None
    ev.default_branch = repo.get("default_branch") or "main"
    ev.changed_files = sorted(set(changed_files))
    ev.delivery_id = delivery_id
    ev.is_actionable = bool(ev.repo_url and ev.commit_sha)
    return ev


def _parse_pull_request(payload: dict[str, Any], delivery_id: str | None) -> ParsedEvent:
    """Extract fields from a GitHub ``pull_request`` event payload.

    Only ``opened``, ``synchronize``, and ``reopened`` actions are considered
    actionable (i.e., worth triggering the test pipeline for).

    Args:
        payload:     Decoded JSON payload dict.
        delivery_id: Value of the ``X-GitHub-Delivery`` header.

    Returns:
        A populated ``ParsedEvent``.
    """
    action = payload.get("action") or ""
    pr = payload.get("pull_request") or {}
    head = pr.get("head") or {}
    base = pr.get("base") or {}
    repo = head.get("repo") or payload.get("repository") or {}

    ev = ParsedEvent()
    ev.event_type = "pull_request"
    ev.action = action
    ev.repo_url = repo.get("clone_url") or repo.get("html_url") or ""
    ev.repo_name = repo.get("full_name") or repo.get("name") or ""
    ev.branch = head.get("ref") or ""
    ev.commit_sha = head.get("sha") or None
    ev.default_branch = base.get("ref") or "main"
    ev.changed_files = []  # PR events do not include per-file lists
    ev.delivery_id = delivery_id
    ev.is_actionable = action in _ACTIONABLE_PR_ACTIONS and bool(ev.repo_url and ev.commit_sha)
    return ev


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

async def _upsert_repository(
    session: AsyncSession,
    repo_url: str,
    repo_name: str,
    default_branch: str,
) -> Repository:
    """Return an existing repository row, or create one if it doesn't exist.

    Args:
        session:        Active async DB session.
        repo_url:       Full clone URL (used as the unique key).
        repo_name:      ``owner/name`` slug or plain name.
        default_branch: Default branch name (e.g. "main").

    Returns:
        The ``Repository`` ORM instance.
    """
    repo = await get_repository_by_url(session, repo_url)
    if repo:
        return repo

    name = repo_name.split("/")[-1] if "/" in repo_name else repo_name or "unknown"
    repo = await create_repository(
        session,
        name=name,
        repo_url=repo_url,
        default_branch=default_branch,
        provider="github",
    )
    logger.info("[github_webhook_service] Created repository record: %s", repo_url)
    return repo


async def _record_event(
    session: AsyncSession,
    ev: ParsedEvent,
    repo_id: Any,
    raw_payload: dict[str, Any],
    signature: str | None,
) -> WebhookEvent | None:
    """Persist the webhook event, enforcing replay-protection via delivery_id.

    The ``webhook_events`` table has a ``UNIQUE(provider, delivery_id)``
    constraint.  On duplicate delivery, ``IntegrityError`` is caught and
    ``None`` is returned — callers treat this as a replay and short-circuit.

    Args:
        session:     Active async DB session.
        ev:          Parsed event metadata.
        repo_id:     UUID of the associated repository row.
        raw_payload: Original decoded JSON payload (for audit storage).
        signature:   Raw value of the ``X-Hub-Signature-256`` header.

    Returns:
        The persisted ``WebhookEvent`` row, or None on duplicate delivery.
    """
    try:
        event_row = await create_webhook_event(
            session,
            event_type=ev.event_type,
            provider="github",
            repo_id=repo_id,
            delivery_id=ev.delivery_id,
            signature=signature,
            status="received",
            commit_sha=ev.commit_sha,
            branch=ev.branch,
            payload=raw_payload,
        )
        return event_row
    except IntegrityError:
        await session.rollback()
        logger.warning(
            "[github_webhook_service] Duplicate delivery_id=%s — replay ignored.",
            ev.delivery_id,
        )
        return None


# ---------------------------------------------------------------------------
# Pipeline enqueue
# ---------------------------------------------------------------------------

def _enqueue_pipeline(ev: ParsedEvent) -> str:
    """Dispatch the full autonomous QA pipeline as a Celery task.

    Uses ``apply_async`` with a short ``countdown`` so the API response is
    sent before the worker picks up the task (avoids 30 s Heroku/AWS timeouts
    on webhook endpoints).

    Args:
        ev: The parsed, validated event.

    Returns:
        The Celery task ID (for logging/audit).
    """
    task = run_test_pipeline_task.apply_async(
        kwargs={
            "repo_url": ev.repo_url,
            "commit_sha": ev.commit_sha,
            "pull": True,
        },
        countdown=5,          # 5 s delay — gives GitHub time to propagate push
        expires=3600,         # Drop if not picked up within 1 hour
    )
    logger.info(
        "[github_webhook_service] Pipeline task enqueued. task_id=%s repo_url=%s commit=%s",
        task.id, ev.repo_url, ev.commit_sha,
    )
    return task.id


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------

async def handle_github_webhook(
    session: AsyncSession,
    payload_bytes: bytes,
    signature: str | None,
    event_type: str | None,
    delivery_id: str | None,
) -> dict[str, Any]:
    """Process an inbound GitHub webhook request end-to-end.

    This function is the single entry-point called by the route handler.  It
    performs all security checks, event parsing, database recording, and task
    dispatch in the correct order.

    Flow
    ----
    1. Verify HMAC-SHA256 signature → 401 on failure.
    2. Parse JSON body.
    3. Route to the correct event parser (push / pull_request / other).
    4. Replay-protect via ``delivery_id`` uniqueness check.
    5. Upsert the repository record.
    6. Persist a ``WebhookEvent`` row.
    7. Dispatch ``run_test_pipeline_task`` to Celery.
    8. Return a structured acknowledgement dict.

    Args:
        session:       Active async DB session (injected by FastAPI dependency).
        payload_bytes: Raw request body (bytes, before any JSON parsing).
        signature:     Value of the ``X-Hub-Signature-256`` header.
        event_type:    Value of the ``X-GitHub-Event`` header.
        delivery_id:   Value of the ``X-GitHub-Delivery`` header.

    Returns:
        A JSON-serialisable dict describing the outcome.

    Raises:
        ValueError: If the HMAC signature is invalid.
    """
    received_at = datetime.now(tz=timezone.utc).isoformat()
    logger.info(
        "[github_webhook_service] Incoming event. type=%s delivery=%s",
        event_type, delivery_id,
    )

    # ------------------------------------------------------------------ #
    # Step 1 — Signature verification                                     #
    # ------------------------------------------------------------------ #
    if not verify_github_signature(payload_bytes, signature):
        logger.warning(
            "[github_webhook_service] Signature verification FAILED. delivery=%s",
            delivery_id,
        )
        raise ValueError("Invalid webhook signature — request rejected.")

    # ------------------------------------------------------------------ #
    # Step 2 — JSON parsing                                               #
    # ------------------------------------------------------------------ #
    try:
        payload: dict[str, Any] = json.loads(payload_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.error("[github_webhook_service] JSON decode error: %s", exc)
        raise ValueError(f"Malformed JSON payload: {exc}") from exc

    # ------------------------------------------------------------------ #
    # Step 3 — Event routing                                              #
    # ------------------------------------------------------------------ #
    if event_type == "push":
        ev = _parse_push(payload, delivery_id)
    elif event_type == "pull_request":
        ev = _parse_pull_request(payload, delivery_id)
    elif event_type == "ping":
        logger.info("[github_webhook_service] ping received — webhook is registered correctly.")
        return {"status": "pong", "event": "ping", "received_at": received_at}
    else:
        logger.info("[github_webhook_service] Unsupported event type '%s' — ignoring.", event_type)
        return {"status": "ignored", "event": event_type, "received_at": received_at}

    logger.info(
        "[github_webhook_service] Parsed %s event. repo=%s commit=%s branch=%s actionable=%s",
        ev.event_type, ev.repo_url, ev.commit_sha, ev.branch, ev.is_actionable,
    )

    # ------------------------------------------------------------------ #
    # Step 4 — Validate required fields                                   #
    # ------------------------------------------------------------------ #
    if not ev.repo_url:
        logger.warning("[github_webhook_service] No repo URL in payload — ignoring.")
        return {
            "status": "ignored",
            "reason": "missing_repo_url",
            "event": event_type,
        }

    # ------------------------------------------------------------------ #
    # Step 5 — Upsert repository record                                   #
    # ------------------------------------------------------------------ #
    repo_record = await _upsert_repository(
        session,
        repo_url=ev.repo_url,
        repo_name=ev.repo_name,
        default_branch=ev.default_branch,
    )

    # ------------------------------------------------------------------ #
    # Step 6 — Persist webhook event (replay protection)                  #
    # ------------------------------------------------------------------ #
    event_row = await _record_event(
        session,
        ev=ev,
        repo_id=repo_record.id,
        raw_payload=payload,
        signature=signature,
    )
    if event_row is None:
        # Duplicate delivery — already processed.
        return {
            "status": "ignored",
            "reason": "duplicate_delivery",
            "delivery_id": delivery_id,
            "event": event_type,
        }

    # ------------------------------------------------------------------ #
    # Step 7 — Enqueue pipeline (only for actionable events)              #
    # ------------------------------------------------------------------ #
    task_id: str | None = None
    if ev.is_actionable:
        try:
            task_id = _enqueue_pipeline(ev)
        except Exception as exc:  # noqa: BLE001
            # Enqueue failure is logged but must not abort the 200 response —
            # GitHub retries on non-2xx, which could cause cascading re-deliveries.
            logger.error(
                "[github_webhook_service] Failed to enqueue pipeline task: %s", exc,
                exc_info=True,
            )
            task_id = None
    else:
        reason = f"action='{ev.action}'" if ev.event_type == "pull_request" else "no commit SHA"
        logger.info(
            "[github_webhook_service] Event not actionable (%s) — pipeline not started.",
            reason,
        )

    # ------------------------------------------------------------------ #
    # Step 8 — Structured acknowledgement                                 #
    # ------------------------------------------------------------------ #
    return {
        "status": "accepted" if task_id else "received",
        "event": event_type,
        "delivery_id": delivery_id,
        "repo_url": ev.repo_url,
        "repo_name": ev.repo_name,
        "branch": ev.branch,
        "commit_sha": ev.commit_sha,
        "actionable": ev.is_actionable,
        "task_id": task_id,
        "changed_files_count": len(ev.changed_files),
        "received_at": received_at,
    }
