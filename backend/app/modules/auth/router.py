from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.modules.auth.schemas import AuthToken, LoginRequest, RegisterRequest, UserRead
from app.modules.auth.service import authenticate_user, issue_tokens_for_user, list_users, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, session: AsyncSession = Depends(get_db)) -> UserRead:
    user = await register_user(
        session,
        email=payload.email,
        username=payload.username,
        display_name=payload.display_name,
        password=payload.password,
    )
    return UserRead(
        id=user.id,
        email=user.email,
        username=user.username,
        display_name=user.display_name,
        is_active=user.is_active,
        email_verified=user.email_verified,
    )


@router.post("/login", response_model=AuthToken)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_db)) -> AuthToken:
    user = await authenticate_user(session, email=payload.email, password=payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token_payload = issue_tokens_for_user(user)
    return AuthToken(
        access_token=str(token_payload["access_token"]),
        refresh_token=str(token_payload["refresh_token"]),
        expires_in=int(token_payload["expires_in"]),
    )


@router.get("/users", response_model=list[UserRead])
async def get_users(session: AsyncSession = Depends(get_db)) -> list[UserRead]:
    users = await list_users(session)
    return [
        UserRead(
            id=user.id,
            email=user.email,
            username=user.username,
            display_name=user.display_name,
            is_active=user.is_active,
            email_verified=user.email_verified,
        )
        for user in users
    ]
