"""Authentication routes for JWT login and registration."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_async_session
from app.dependencies.jwt_auth import get_current_user
from app.schemas.auth_schema import TokenResponse, UserCreate, UserLogin, UserResponse
from app.services.auth_service import (
    AuthServiceError,
    DuplicateUserError,
    InactiveUserError,
    InvalidCredentialsError,
    authenticate_user,
    create_access_token_for_user,
    register_user,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: UserCreate,
    session: AsyncSession = Depends(get_async_session),
):
    try:
        user = await register_user(
            session,
            email=body.email,
            password=body.password,
            full_name=body.full_name,
        )
    except DuplicateUserError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except AuthServiceError as exc:
        logger.error("Registration failed for %s", body.email, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    body: UserLogin,
    session: AsyncSession = Depends(get_async_session),
):
    try:
        user = await authenticate_user(session, email=body.email, password=body.password)
        token = create_access_token_for_user(user)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InactiveUserError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except AuthServiceError as exc:
        logger.error("Login failed for %s", body.email, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    return TokenResponse(access_token=token, expires_in=settings.JWT_EXPIRE_MINUTES * 60)


@router.get("/me", response_model=UserResponse)
async def me(current_user=Depends(get_current_user)):
    return current_user
