from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import create_token
from app.database import AsyncSessionLocal
from app.main import app, verify_subscription_access
from app.modules.auth.service import revoke_token
from app.modules.channels.models import Channel, ChannelMember
from app.modules.conversations.models import Conversation, ConversationMember

client = TestClient(app)


def test_websocket_missing_token_rejected_immediately() -> None:
    # Connecting with no token must close / fail immediately
    with pytest.raises(Exception):
        with client.websocket_connect("/ws"):
            pass


def test_websocket_revoked_token_rejected_immediately() -> None:
    token = create_token("user-ws-test-1", token_type="access", email="ws@example.com")
    revoke_token(token)

    with pytest.raises(Exception):
        with client.websocket_connect(f"/ws?token={token}"):
            pass


def test_websocket_invalid_token_rejected_immediately() -> None:
    with pytest.raises(Exception):
        with client.websocket_connect("/ws?token=invalid.jwt.token"):
            pass


def test_websocket_verified_token_connects_and_binds_claims() -> None:
    token = create_token("user-ws-auth-1", token_type="access", email="wsauth@example.com", workspace_id="ws-alpha", role="member")
    with client.websocket_connect(f"/ws?token={token}") as websocket:
        data = websocket.receive_json()
        assert data["event_type"] == "connected"
        payload = data["payload"]
        assert payload["client_id"] == "user-ws-auth-1"
        assert payload["workspace_id"] == "ws-alpha"
        assert payload["role"] == "member"


@pytest.mark.asyncio
async def test_subscription_authorization_logic() -> None:
    class MockDbSession:
        def __init__(self, entities: dict) -> None:
            self.entities = entities

        async def get(self, model, ident):
            return self.entities.get(f"{model.__name__}:{ident}")

        async def scalar(self, statement):
            stmt_str = str(statement).lower()
            if "channel_members" in stmt_str:
                for k, v in self.entities.items():
                    if k.startswith("ChannelMember:") and "user-1" in k:
                        return v
            elif "conversation_members" in stmt_str:
                for k, v in self.entities.items():
                    if k.startswith("ConversationMember:") and "user-1" in k:
                        return v
            return None

    public_ch = Channel(id="ch-public-1", workspace_id="ws-alpha", name="general", is_private=False)
    private_ch = Channel(id="ch-priv-1", workspace_id="ws-alpha", name="secret", is_private=True)
    other_ws_ch = Channel(id="ch-other-1", workspace_id="ws-beta", name="general-beta", is_private=False)
    conv_dm = Conversation(id="conv-1", workspace_id="ws-alpha", type="dm", created_by="user-1")

    session = MockDbSession({
        "Channel:ch-public-1": public_ch,
        "Channel:ch-priv-1": private_ch,
        "Channel:ch-other-1": other_ws_ch,
        "Conversation:conv-1": conv_dm,
    })

    # 1. Public channel in user's workspace is authorized
    auth1 = await verify_subscription_access(session, user_id="user-1", workspace_id="ws-alpha", target_id="ch-public-1", user_role="member")
    assert auth1 is True

    # 2. Private channel without membership is rejected
    auth2 = await verify_subscription_access(session, user_id="user-1", workspace_id="ws-alpha", target_id="ch-priv-1", user_role="member")
    assert auth2 is False

    # 3. Channel from another workspace (cross-tenant) is rejected
    auth3 = await verify_subscription_access(session, user_id="user-1", workspace_id="ws-alpha", target_id="ch-other-1", user_role="member")
    assert auth3 is False

    # 4. Unknown channel is rejected
    auth4 = await verify_subscription_access(session, user_id="user-1", workspace_id="ws-alpha", target_id="ch-nonexistent", user_role="member")
    assert auth4 is False
