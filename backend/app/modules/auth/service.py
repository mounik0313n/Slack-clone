from __future__ import annotations

from argon2 import PasswordHasher
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import create_token, settings
from app.modules.auth.models import User

ph = PasswordHasher()


async def register_user(session: AsyncSession, *, email: str, username: str, display_name: str, password: str) -> User:
    existing = await session.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    user = User(
        id="user-" + email.split("@")[0],
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


async def fetch_user_by_id(session: AsyncSession, user_id: str) -> User | None:
    return await session.get(User, user_id)


async def list_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).order_by(User.email))
    return list(result.scalars().all())
