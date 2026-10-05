from __future__ import annotations

from app.config import create_token, decode_token
from app.modules.auth.models import User
from app.modules.auth.service import issue_tokens_for_user


def test_create_and_decode_access_token() -> None:
    token = create_token("user-123", token_type="access", email="user@example.com", role="member")
    claims = decode_token(token)
    assert claims["sub"] == "user-123"
    assert claims["type"] == "access"
    assert claims["email"] == "user@example.com"


def test_issue_tokens_for_user() -> None:
    user = User(
        id="user-123",
        email="user@example.com",
        username="demo-user",
        display_name="Demo User",
        password_hash="hashed-value",
        is_active=True,
        email_verified=True,
    )

    tokens = issue_tokens_for_user(user)
    assert isinstance(tokens["access_token"], str)
    assert isinstance(tokens["refresh_token"], str)
    assert tokens["expires_in"] > 0
