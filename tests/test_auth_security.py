from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.config import create_token
from app.modules.auth.models import User
from app.modules.auth.service import (
    authenticate_user,
    is_token_revoked,
    issue_tokens_for_user,
    ph,
    refresh_user_tokens,
    request_password_reset,
    reset_password,
    revoke_token,
)


class MockSession:
    def __init__(self, users: dict[str, User] | None = None) -> None:
        self.users = users or {}
        self.added = []

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, User):
            self.users[obj.id] = obj

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass

    async def get(self, model, ident):
        if model is User:
            return self.users.get(ident)
        return None

    async def scalar(self, statement):
        # Return first user matching email if query targets User
        for u in self.users.values():
            return u
        return None


def test_password_hasher_verifies_valid_password() -> None:
    password = "SuperSecretPassword123!"
    hashed = ph.hash(password)
    assert ph.verify(hashed, password) is True


def test_token_revocation_lifecycle() -> None:
    test_token = "sample-revocable-token-abc"
    assert is_token_revoked(test_token) is False
    revoke_token(test_token)
    assert is_token_revoked(test_token) is True


@pytest.mark.asyncio
async def test_refresh_token_rotation_and_replay_prevention() -> None:
    user = User(
        id="user-rotate-1",
        email="rotate@example.com",
        username="rotate_user",
        display_name="Rotate User",
        password_hash=ph.hash("password"),
        is_active=True,
        email_verified=True,
    )
    session = MockSession(users={user.id: user})

    initial_tokens = issue_tokens_for_user(user)
    refresh_tok = initial_tokens["refresh_token"]

    # First refresh succeeds and rotates token
    new_tokens = await refresh_user_tokens(session, refresh_tok)
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens
    assert new_tokens["refresh_token"] != refresh_tok

    # Replay of the old refresh token must be rejected
    with pytest.raises(HTTPException) as exc_info:
        await refresh_user_tokens(session, refresh_tok)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_password_reset_workflow() -> None:
    user = User(
        id="user-reset-1",
        email="reset@example.com",
        username="reset_user",
        display_name="Reset User",
        password_hash=ph.hash("old_password_123"),
        is_active=True,
        email_verified=True,
    )
    session = MockSession(users={user.id: user})

    token = await request_password_reset(session, "reset@example.com")
    assert isinstance(token, str)
    assert len(token) > 10

    # Execute password reset
    success = await reset_password(session, token=token, new_password="new_password_456")
    assert success is True
    assert ph.verify(user.password_hash, "new_password_456") is True

    # Reusing the same reset token fails
    with pytest.raises(HTTPException) as exc_info:
        await reset_password(session, token=token, new_password="another_password")
    assert exc_info.value.status_code == 400
