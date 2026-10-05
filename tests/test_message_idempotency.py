from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.core.outbox.service import emit_outbox_event
from app.modules.messages.schemas import MessageCreate
from app.modules.messages.service import create_message


def test_message_create_accepts_client_message_id() -> None:
    payload = MessageCreate(
        workspace_id="ws-1",
        channel_id="ch-1",
        author_id="user-1",
        body="hello",
        client_message_id="client-123",
    )
    assert payload.client_message_id == "client-123"


@pytest.mark.asyncio
async def test_create_message_reuses_existing_client_message_id() -> None:
    class FakeResult:
        def __init__(self, values):
            self._values = values

        def scalars(self):
            return SimpleNamespace(
                all=lambda: list(self._values),
                first=lambda: self._values[0] if self._values else None,
            )

    class FakeSession:
        def __init__(self) -> None:
            self.calls = 0
            self.saved = []

        async def execute(self, query):
            self.calls += 1
            if self.calls == 1:
                return FakeResult([
                    SimpleNamespace(
                        id="msg-existing",
                        workspace_id="ws-1",
                        channel_id="ch-1",
                        author_id="user-1",
                        sequence=10,
                        body="hello",
                        thread_id=None,
                        created_at=datetime.now(timezone.utc),
                        updated_at=None,
                    )
                ])
            return FakeResult([])

        def add(self, obj):
            self.saved.append(obj)

        async def commit(self):
            return None

        async def refresh(self, obj):
            return None

    session = FakeSession()
    message = await create_message(
        session,
        workspace_id="ws-1",
        channel_id="ch-1",
        author_id="user-1",
        body="hello",
        thread_id=None,
        client_message_id="client-123",
    )

    assert message.id == "msg-existing"
    assert session.calls == 1


@pytest.mark.asyncio
async def test_emit_outbox_event_persists_event() -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.saved = []

        def add(self, obj):
            self.saved.append(obj)

        async def flush(self):
            return None

    session = FakeSession()
    event = await emit_outbox_event(
        session,
        event_type="message.created",
        aggregate_type="message",
        aggregate_id="msg-1",
        payload={"message_id": "msg-1"},
    )

    assert event.event_type == "message.created"
    assert event.aggregate_id == "msg-1"
    assert len(session.saved) == 1
