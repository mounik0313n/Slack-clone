from __future__ import annotations

import io
from datetime import datetime, timezone
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import create_token
from app.main import app
from app.modules.ai.router import summarize_channel_endpoint
from app.modules.ai.schemas import SummarizeRequest
from app.modules.channels.models import Channel, ChannelMember
from app.modules.files.models import FileAttachment
from app.modules.files.router import get_file_metadata_endpoint, upload_file_endpoint
from app.modules.messages.models import Message
from app.modules.search.router import search_messages_endpoint
from app.modules.sync.router import sync_snapshot

client = TestClient(app)


def test_unauthenticated_endpoints_reject_with_401() -> None:
    # 1. Search
    r_search = client.get("/api/v1/search/messages?query=test")
    assert r_search.status_code == 401

    # 2. Files
    r_file = client.get("/api/v1/files/file-1")
    assert r_file.status_code == 401

    # 3. AI summarize
    r_ai = client.post("/api/v1/ai/summarize", json={"channel_id": "ch-1"})
    assert r_ai.status_code == 401

    # 4. Sync
    r_sync = client.get("/api/v1/sync")
    assert r_sync.status_code == 401


@pytest.mark.asyncio
async def test_cross_workspace_search_rejected() -> None:
    class MockSearchSession:
        pass

    caller_ws_alpha = {"user_id": "user-alpha", "workspace_id": "ws-alpha", "role": "member", "permissions": ["message.read"]}

    # Trying to search messages in ws-beta with ws-alpha credentials
    with pytest.raises(PermissionError):
        await search_messages_endpoint(
            query="secret",
            workspace_id="ws-beta",
            session=MockSearchSession(),
            current_user=caller_ws_alpha,
        )


@pytest.mark.asyncio
async def test_cross_workspace_file_access_rejected() -> None:
    class MockFileSession:
        async def get(self, model, ident):
            return FileAttachment(
                id="file-beta-1",
                workspace_id="ws-beta",  # Belongs to ws-beta
                uploader_id="user-beta",
                filename="beta_confidential.pdf",
                content_type="application/pdf",
                size_bytes=1000,
                storage_key="uploads/file.pdf",
                created_at=datetime.now(timezone.utc),
            )

    caller_ws_alpha = {"user_id": "user-alpha", "workspace_id": "ws-alpha", "role": "member", "permissions": ["message.read"]}

    with pytest.raises(PermissionError):
        await get_file_metadata_endpoint("file-beta-1", session=MockFileSession(), current_user=caller_ws_alpha)


@pytest.mark.asyncio
async def test_private_channel_ai_summary_access_control() -> None:
    class MockAiSession:
        async def get(self, model, ident):
            if ident == "ch-secret":
                return Channel(id="ch-secret", workspace_id="ws-alpha", name="secret", is_private=True)
            return None

        async def scalar(self, statement):
            # User is not a member of the private channel
            return None

    non_member_caller = {"user_id": "user-guest", "workspace_id": "ws-alpha", "role": "member", "permissions": ["message.read"]}

    with pytest.raises(HTTPException) as exc_info:
        await summarize_channel_endpoint(
            payload=SummarizeRequest(channel_id="ch-secret"),
            session=MockAiSession(),
            current_user=non_member_caller,
        )
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_cross_workspace_sync_rejected() -> None:
    class MockSyncSession:
        pass

    caller_ws_alpha = {"user_id": "user-alpha", "workspace_id": "ws-alpha", "role": "member", "permissions": []}

    with pytest.raises(PermissionError):
        await sync_snapshot(
            workspace_id="ws-beta",  # Cross-workspace attempt
            session=MockSyncSession(),
            current_user=caller_ws_alpha,
        )
