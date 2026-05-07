"""Authentication utilities for FastAPI endpoints."""

from __future__ import annotations

import logging
import os

from fastapi import Depends, Header, HTTPException, status


logger = logging.getLogger(__name__)

# Environment variable that holds the shared API key.
_API_KEY_ENV = "API_KEY"


def verify_api_key(api_key: str | None = Header(default=None, alias="X-API-Key")) -> str:
    """Validate the API key supplied in the request header.

    Args:
        api_key: API key provided via the X-API-Key header.

    Returns:
        The validated API key value.

    Raises:
        HTTPException: 401 Unauthorized if the key is missing or invalid.
    """

    configured_key = os.getenv(_API_KEY_ENV, "").strip()

    if not configured_key:
        logger.warning("API key authentication enabled but %s is not set.", _API_KEY_ENV)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is not configured.",
            headers={"WWW-Authenticate": "API-Key"},
        )

    if not api_key or api_key.strip() != configured_key:
        logger.info("Invalid or missing API key provided.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "API-Key"},
        )

    logger.debug("API key validated successfully.")
    return api_key


# Reusable dependency for route protection.
api_key_dependency = Depends(verify_api_key)

# Future JWT expansion note: replace the header check with a JWT validation
# dependency while keeping the same Depends-based injection pattern.
