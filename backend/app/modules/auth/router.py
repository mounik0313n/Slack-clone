from __future__ import annotations

import time
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.modules.auth.schemas import (
    AuthToken,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    UserProfile,
    UserRead,
)
from app.modules.auth.service import (
    authenticate_user,
    fetch_user_by_id,
    issue_tokens_for_user,
    list_users,
    refresh_user_tokens,
    register_user,
    request_password_reset,
    reset_password,
    revoke_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory sliding window rate limiter: IP -> list of timestamps
_rate_limit_records: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_MAX_ATTEMPTS = 10
RATE_LIMIT_WINDOW_SECONDS = 60.0


def check_rate_limit(client_ip: str) -> None:
    now = time.time()
    timestamps = _rate_limit_records[client_ip]
    _rate_limit_records[client_ip] = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW_SECONDS]
    if len(_rate_limit_records[client_ip]) >= RATE_LIMIT_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Please try again in 1 minute.",
        )
    _rate_limit_records[client_ip].append(now)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> UserRead:
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(client_ip)

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
async def login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> AuthToken:
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(client_ip)

    user = await authenticate_user(session, email=payload.email, password=payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token_payload = issue_tokens_for_user(user)
    return AuthToken(
        access_token=str(token_payload["access_token"]),
        refresh_token=str(token_payload["refresh_token"]),
        expires_in=int(token_payload["expires_in"]),
    )


@router.post("/refresh", response_model=AuthToken)
async def refresh_tokens(
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_db),
) -> AuthToken:
    tokens = await refresh_user_tokens(session, payload.refresh_token)
    return AuthToken(
        access_token=str(tokens["access_token"]),
        refresh_token=str(tokens["refresh_token"]),
        expires_in=int(tokens["expires_in"]),
    )


@router.get("/me", response_model=UserProfile)
async def get_me(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserProfile:
    user = await fetch_user_by_id(session, current_user["user_id"])
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserProfile(
        id=user.id,
        email=user.email,
        username=user.username,
        display_name=user.display_name,
        is_active=user.is_active,
        email_verified=user.email_verified,
        role=current_user.get("role", "member"),
        roles=current_user.get("roles", ["member"]),
        permissions=current_user.get("permissions", []),
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(current_user: dict = Depends(get_current_user)) -> dict[str, str]:
    token = current_user.get("token")
    if token:
        revoke_token(token)
    return {"status": "logged_out"}


@router.post("/password-reset/request")
async def password_reset_request_endpoint(
    payload: PasswordResetRequest,
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    reset_token = await request_password_reset(session, payload.email)
    return {"message": "If this email is registered, reset instructions have been created.", "reset_token": reset_token}


@router.post("/password-reset/confirm")
async def password_reset_confirm_endpoint(
    payload: PasswordResetConfirm,
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await reset_password(session, token=payload.token, new_password=payload.new_password)
    return {"status": "password_updated"}


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
