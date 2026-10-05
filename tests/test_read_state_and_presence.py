from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.presence.service import PresenceService
from app.modules.read_states.service import mark_channel_read, unread_count_for_channel


@pytest.mark.asyncio
async def test_mark_channel_read_tracks_last_sequence() -> None:
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
    state = await mark_channel_read(
        session,
        workspace_id="ws-1",
        channel_id="ch-1",
        user_id="user-1",
        last_read_sequence=10,
        last_read_message_id="msg-10",
    )

    assert state.user_id == "user-1"
    assert state.last_read_sequence == 10
    assert state.last_read_message_id == "msg-10"


@pytest.mark.asyncio
async def test_unread_count_uses_sequence_gap() -> None:
    class FakeResult:
        def __init__(self, values):
            self._values = values

        def scalars(self):
            return SimpleNamespace(all=lambda: list(self._values))

    class FakeSession:
        async def execute(self, query):
            return FakeResult([12, 15, 40])

    count = await unread_count_for_channel(
        FakeSession(),
        workspace_id="ws-1",
        channel_id="ch-1",
        user_id="user-1",
        last_read_sequence=10,
    )

    assert count == 3


def test_presence_service_tracks_status() -> None:
    service = PresenceService()
    service.set_presence("user-1", "online")
    assert service.get_presence("user-1") == "online"
    assert service.get_online_users() == {"user-1"}
