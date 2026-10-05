from __future__ import annotations

import pytest

from app.modules.mentions.service import detect_mentions, save_mentions_for_message
from app.modules.notifications.service import create_notification, mark_notification_read, list_notifications_for_user


@pytest.mark.asyncio
async def test_detect_mentions_in_message() -> None:
    mentions = detect_mentions("Hello @alice and @here, welcome @bob")
    assert {m["user_id"] for m in mentions} == {"alice", "bob", "here"}
    assert any(m["type"] == "user" for m in mentions)
    assert any(m["type"] == "channel" for m in mentions)


@pytest.mark.asyncio
async def test_save_mentions_for_message() -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.saved = []

        def add(self, obj):
            self.saved.append(obj)

        async def commit(self):
            return None

        async def refresh(self, obj):
            return None

    session = FakeSession()
    mentions = await save_mentions_for_message(
        session,
        organization_id="org-1",
        workspace_id="ws-1",
        conversation_id="conv-1",
        message_id="msg-1",
        body="Hello @alice and @bob",
        user_lookup={"alice": "user-1", "bob": "user-2"},
    )

    assert len(mentions) == 2
    assert {m.mentioned_user_id for m in mentions} == {"user-1", "user-2"}
    assert len(session.saved) == 2


@pytest.mark.asyncio
async def test_create_and_mark_notification_read() -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.saved = []
            self.read = []

        def add(self, obj):
            self.saved.append(obj)

        def delete(self, obj):
            self.saved.remove(obj)

        async def commit(self):
            return None

        async def refresh(self, obj):
            return None

    session = FakeSession()
    notification = await create_notification(
        session,
        organization_id="org-1",
        workspace_id="ws-1",
        recipient_user_id="user-2",
        actor_user_id="user-1",
        type="MENTION",
        conversation_id="conv-1",
        message_id="msg-1",
        payload={"body": "Hello @user-2"},
    )

    assert notification.recipient_user_id == "user-2"
    assert notification.type == "MENTION"

    updated = await mark_notification_read(session, notification_id=notification.id, user_id="user-2")
    assert updated is True

    notifications = await list_notifications_for_user(session, user_id="user-2")
    assert len(notifications) >= 1
