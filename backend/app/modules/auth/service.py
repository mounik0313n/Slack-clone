from __future__ import annotations

import secrets
from argon2 import PasswordHasher
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import create_token, decode_token, settings
from app.modules.auth.models import User

ph = PasswordHasher()
_revoked_tokens: set[str] = set()
_password_reset_tokens: dict[str, str] = {}  # token -> user_id


def is_token_revoked(token: str) -> bool:
    return token in _revoked_tokens


def revoke_token(token: str) -> None:
    _revoked_tokens.add(token)


async def register_user(session: AsyncSession, *, email: str, username: str, display_name: str, password: str) -> User:
    existing = await session.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    user = User(
        id="user-" + secrets.token_hex(6),
        email=email,
        username=username,
        display_name=display_name,
        password_hash=ph.hash(password),
        is_active=True,
        email_verified=False,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate_user(session: AsyncSession, *, email: str, password: str) -> User | None:
    user = await session.scalar(select(User).where(User.email == email))
    if user is None:
        return None
    try:
        ph.verify(user.password_hash, password)
        return user
    except Exception:
        return None


def issue_tokens_for_user(user: User) -> dict[str, str | int]:
    permissions = [
        "workspace.read",
        "channel.read",
        "channel.create",
        "message.create",
        "message.read",
        "member.read",
    ]
    access_token = create_token(
        user.id,
        token_type="access",
        expires_minutes=settings.jwt_access_token_expire_minutes,
        email=user.email,
        role="member",
        roles=["member"],
        permissions=permissions,
    )
    refresh_token = create_token(
        user.id,
        token_type="refresh",
        expires_minutes=settings.jwt_refresh_token_expire_days * 24 * 60,
        email=user.email,
        role="member",
        roles=["member"],
        permissions=permissions,
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": settings.jwt_access_token_expire_minutes * 60,
    }


async def refresh_user_tokens(session: AsyncSession, refresh_token: str) -> dict[str, str | int]:
    if is_token_revoked(refresh_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has been revoked")

    try:
        claims = decode_token(refresh_token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc

    if claims.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type for refresh")

    user_id = str(claims.get("sub", ""))
    user = await session.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    # Rotate refresh token to prevent replay
    revoke_token(refresh_token)
    return issue_tokens_for_user(user)


async def request_password_reset(session: AsyncSession, email: str) -> str:
    user = await session.scalar(select(User).where(User.email == email))
    if not user:
        # Avoid user enumeration in public responses
        return "If the account exists, a reset token has been issued."

    reset_token = secrets.token_urlsafe(32)
    _password_reset_tokens[reset_token] = user.id
    return reset_token


async def reset_password(session: AsyncSession, *, token: str, new_password: str) -> bool:
    user_id = _password_reset_tokens.pop(token, None)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.password_hash = ph.hash(new_password)
    await session.commit()
    return True


async def fetch_user_by_id(session: AsyncSession, user_id: str) -> User | None:
    return await session.get(User, user_id)


async def list_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).order_by(User.email))
    return list(result.scalars().all())
