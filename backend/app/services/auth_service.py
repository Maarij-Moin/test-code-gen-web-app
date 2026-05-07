"""Authentication services for registration and login flows."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user_model import User


logger = logging.getLogger(__name__)


class AuthServiceError(Exception):
    """Base auth service exception."""


class DuplicateUserError(AuthServiceError):
    """Raised when a user with the same email already exists."""


class InvalidCredentialsError(AuthServiceError):
    """Raised when credentials are invalid."""


class InactiveUserError(AuthServiceError):
    """Raised when the user account is inactive."""


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    normalized_email = email.strip().lower()
    result = await session.execute(
        select(User).where(func.lower(User.email) == normalized_email)
    )
    return result.scalar_one_or_none()


async def register_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: str | None = None,
) -> User:
    normalized_email = email.strip().lower()
    user = User(
        email=normalized_email,
        hashed_password=hash_password(password),
        full_name=full_name,
    )

    session.add(user)
    try:
        await session.commit()
        await session.refresh(user)
    except IntegrityError as exc:
        await session.rollback()
        logger.info("Duplicate registration attempt for %s", normalized_email)
        raise DuplicateUserError("User already exists") from exc
    except SQLAlchemyError as exc:
        await session.rollback()
        logger.error("Failed to register user %s", normalized_email, exc_info=True)
        raise AuthServiceError("Registration failed") from exc

    logger.info("Registered user %s", normalized_email)
    return user


async def authenticate_user(
    session: AsyncSession, *, email: str, password: str
) -> User:
    user = await get_user_by_email(session, email)
    if not user or not verify_password(password, user.hashed_password):
        logger.info("Invalid login attempt for %s", email)
        raise InvalidCredentialsError("Invalid credentials")
    if not user.is_active:
        logger.warning("Inactive account login attempt for %s", email)
        raise InactiveUserError("User is inactive")

    user.last_login_at = datetime.now(timezone.utc)
    session.add(user)
    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        logger.warning("Failed to update last_login_at for %s", user.email, exc_info=True)

    return user


def create_access_token_for_user(user: User) -> str:
    return create_access_token(subject=user.email)
