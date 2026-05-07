"""Authentication routes for JWT login and registration."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.db.session import get_async_session
from app.schemas.auth_schema import TokenResponse, UserCreate, UserLogin, UserResponse
from app.services.user_service import authenticate_user, create_user, get_user_by_email
from app.dependencies.jwt_auth import get_current_user


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    body: UserCreate,
    session: AsyncSession = Depends(get_async_session),
):
    existing = await get_user_by_email(session, body.email)
    if existing:
        raise HTTPException(status_code=409, detail="User already exists")
    user = await create_user(session, body.email, body.password, body.full_name)
    return user


@router.post("/login", response_model=TokenResponse)
async def login_user(
    body: UserLogin,
    session: AsyncSession = Depends(get_async_session),
):
    user = await authenticate_user(session, body.email, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(subject=user.email)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def read_me(current_user=Depends(get_current_user)):
    return current_user
