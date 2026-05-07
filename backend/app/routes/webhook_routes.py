"""
GitHub Webhook Routes — production FastAPI router.

Endpoints
---------
POST /webhooks/github
    Receive GitHub push and pull_request events.
    Verifies signature, enforces replay protection, enqueues the
    autonomous test-generation pipeline.

GET  /webhooks/health
    Lightweight check confirming the webhook router is mounted and
    GITHUB_WEBHOOK_SECRET is configured.

Security
--------
- Raw request body is read BEFORE JSON parsing so the HMAC digest is
  computed over the exact bytes GitHub signed.
- The ``X-Hub-Signature-256`` and ``X-GitHub-Delivery`` headers are
  extracted as FastAPI Header dependencies — missing values arrive as None
  and are handled inside ``github_webhook_service``.
- Signature failures raise ``ValueError`` which is mapped to HTTP 401.
- All other unexpected errors are caught and returned as HTTP 500 JSON
  (never leaking internal tracebacks to the caller).

Response contract
-----------------
Every response is a JSON object with at least these keys:

    {
        "status":      "accepted" | "received" | "ignored" | "pong",
        "event":       <event-type string or null>,
        "delivery_id": <UUID string or null>,
        ...event-specific fields...
    }

HTTP 202 is returned for successfully enqueued pipeline tasks so that
GitHub's webhook delivery log clearly distinguishes accepted events from
silently ignored ones.
"""

from __future__ import annotations

import logging
import traceback
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.services.github_webhook_service import handle_github_webhook

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_session():
    """Yield a short-lived async session outside the FastAPI Depends system.

    The webhook endpoint reads the raw body before yielding to any dependency,
    so we manage the session lifecycle manually inside the route function.
    This avoids the session being created before the body is fully consumed.
    """
    async with AsyncSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/github",
    status_code=status.HTTP_202_ACCEPTED,
    summary="GitHub webhook receiver",
    response_description="Structured acknowledgement of the received event.",
    responses={
        202: {"description": "Event accepted and pipeline task enqueued."},
        200: {"description": "Event received but not actionable (ignored or pong)."},
        401: {"description": "HMAC signature verification failed."},
        500: {"description": "Unexpected server error during event processing."},
    },
)
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(
        default=None,
        alias="X-Hub-Signature-256",
        description="HMAC-SHA256 signature of the request body (``sha256=<hex>``).",
    ),
    x_github_event: str | None = Header(
        default=None,
        alias="X-GitHub-Event",
        description="GitHub event type (``push``, ``pull_request``, ``ping``, …).",
    ),
    x_github_delivery: str | None = Header(
        default=None,
        alias="X-GitHub-Delivery",
        description="Unique UUID assigned by GitHub per delivery (replay protection).",
    ),
) -> JSONResponse:
    """Receive and process a GitHub webhook event.

    GitHub sends this endpoint a signed JSON payload for every configured
    event.  The handler:

    1. Reads the raw body bytes (required for signature verification).
    2. Verifies the ``X-Hub-Signature-256`` HMAC signature.
    3. Parses and routes the event (``push`` / ``pull_request`` / other).
    4. Enforces replay protection via the ``X-GitHub-Delivery`` UUID.
    5. Persists a ``WebhookEvent`` database row for auditing.
    6. Enqueues the full autonomous test-generation pipeline task.
    7. Returns a structured JSON acknowledgement.

    **Setup instructions** (GitHub repository → Settings → Webhooks)

    - Payload URL: ``https://<your-domain>/webhooks/github``
    - Content type: ``application/json``
    - Secret: value of ``GITHUB_WEBHOOK_SECRET`` in your ``.env``
    - Events: ``push`` and ``pull_request``
    """
    # ------------------------------------------------------------------ #
    # Read raw bytes FIRST — before any framework body-parsing.           #
    # This is critical: HMAC must be computed over the exact bytes GitHub  #
    # signed, not over a re-serialised version of the parsed JSON.        #
    # ------------------------------------------------------------------ #
    body: bytes = await request.body()

    logger.info(
        "[webhook_routes] POST /webhooks/github  event=%s  delivery=%s  bytes=%d",
        x_github_event, x_github_delivery, len(body),
    )

    # ------------------------------------------------------------------ #
    # Delegate all processing to the service layer.                       #
    # ------------------------------------------------------------------ #
    async with AsyncSessionLocal() as session:
        try:
            result: dict[str, Any] = await handle_github_webhook(
                session=session,
                payload_bytes=body,
                signature=x_hub_signature_256,
                event_type=x_github_event,
                delivery_id=x_github_delivery,
            )
        except ValueError as exc:
            # Signature mismatch or malformed payload — respond 401.
            logger.warning(
                "[webhook_routes] Rejected. delivery=%s reason=%s",
                x_github_delivery, exc,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            # Unexpected error — log full traceback, return 500.
            logger.error(
                "[webhook_routes] Unexpected error. delivery=%s\n%s",
                x_github_delivery,
                traceback.format_exc(),
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "status": "error",
                    "detail": "Internal server error during webhook processing.",
                    "delivery_id": x_github_delivery,
                },
            )

    # Choose the HTTP status code based on the outcome.
    event_status = result.get("status", "received")
    if event_status == "accepted":
        http_code = status.HTTP_202_ACCEPTED
    else:
        http_code = status.HTTP_200_OK

    logger.info(
        "[webhook_routes] Response: status=%s http=%d delivery=%s task=%s",
        event_status, http_code, x_github_delivery, result.get("task_id"),
    )
    return JSONResponse(status_code=http_code, content=result)


@router.get(
    "/health",
    summary="Webhook router health check",
    response_description="Basic configuration status.",
    responses={
        200: {"description": "Webhook router is reachable."},
    },
)
async def webhook_health() -> dict[str, Any]:
    """Confirm the webhook router is mounted and the secret is configured.

    This endpoint does NOT require authentication and is safe to call from
    monitoring tools.  It returns whether ``GITHUB_WEBHOOK_SECRET`` is set
    so operators can detect misconfiguration without exposing the secret
    itself.
    """
    secret_configured = bool(settings.GITHUB_WEBHOOK_SECRET)
    return {
        "status": "ok",
        "webhook_path": "/webhooks/github",
        "secret_configured": secret_configured,
        "supported_events": ["push", "pull_request", "ping"],
        "replay_protection": "enabled (X-GitHub-Delivery uniqueness)",
        "signature_verification": "enabled" if secret_configured else "DISABLED — set GITHUB_WEBHOOK_SECRET",
    }
