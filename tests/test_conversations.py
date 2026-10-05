from __future__ import annotations

import pytest

from app.modules.conversations.service import create_direct_conversation, create_group_conversation, list_conversations_for_user


@pytest.mark.asyncio
async def test_create_direct_conversation() -> None:
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
    conversation = await create_direct_conversation(
        session,
        workspace_id="ws-1",
        user_id_a="user-1",
        user_id_b="user-2",
    )

    assert conversation.workspace_id == "ws-1"
    assert conversation.type == "dm"
    assert len(session.saved) >= 3


@pytest.mark.asyncio
async def test_create_group_conversation() -> None:
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
    conversation = await create_group_conversation(
        session,
        workspace_id="ws-1",
        created_by="user-1",
        name="Design Review",
        member_ids=["user-1", "user-2", "user-3"],
    )

    assert conversation.type == "group_dm"
    assert conversation.name == "Design Review"
    assert len(session.saved) >= 4


@pytest.mark.asyncio
async def test_list_conversations_for_user() -> None:
    class FakeSession:
        def __init__(self) -> None:
            self._conversations = {
                "conv-1": type("Conversation", (), {"id": "conv-1", "workspace_id": "ws-1", "type": "dm", "name": None})(),
                "conv-2": type("Conversation", (), {"id": "conv-2", "workspace_id": "ws-1", "type": "group_dm", "name": "Ops"})(),
            }
            self._members = {
                "user-1": ["conv-1", "conv-2"],
                "user-2": ["conv-1"],
            }

        async def execute(self, query):
            return type("Result", (), {"scalars": lambda self: type("Scalars", (), {"all": lambda self: list(self._owner._conversations.values())})()})()

    session = FakeSession()
    conversations = await list_conversations_for_user(session, workspace_id="ws-1", user_id="user-1")
    assert len(conversations) >= 2
