"""Webhook endpoints for GitHub events."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.services.webhook_service import handle_github_webhook


router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/github")
async def github_webhook(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    x_github_event: str | None = Header(default=None, alias="X-GitHub-Event"),
):
    payload = await request.body()
    try:
        return await handle_github_webhook(
            session=session,
            payload_bytes=payload,
            signature=x_hub_signature_256,
            event=x_github_event,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
