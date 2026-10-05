from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.messages.router import create_message_endpoint
from app.modules.messages.schemas import MessageCreate
from app.realtime.gateway import RealtimeGateway
from app.workers.event_worker import EventWorker


@pytest.mark.asyncio
async def test_realtime_gateway_broadcasts_event() -> None:
    gateway = RealtimeGateway()
    class FakeSocket:
        def __init__(self) -> None:
            self.sent = []

        async def send_json(self, payload):
            self.sent.append(payload)

    socket = FakeSocket()
    gateway.connections["client-1"] = socket
    gateway.subscriptions["client-1"] = {"general"}

    await gateway.broadcast("message.created", {"text": "hello"}, channel="general")

    assert gateway.connections["client-1"].sent[0]["event_type"] == "message.created"


@pytest.mark.asyncio
async def test_message_endpoint_broadcasts_created_event(monkeypatch) -> None:
    fake_gateway = SimpleNamespace(broadcast=AsyncMock())
    monkeypatch.setattr("app.main.realtime_gateway", fake_gateway, raising=False)

    async def fake_create_message(*args, **kwargs):
        return SimpleNamespace(
            id="msg-1",
            workspace_id="ws-1",
            channel_id="ch-1",
            author_id="user-1",
            sequence=7,
            body="hello",
            thread_id=None,
            client_message_id=None,
            created_at=datetime.now(timezone.utc),
            updated_at=None,
        )

    monkeypatch.setattr("app.modules.messages.router.create_message", fake_create_message)

    result = await create_message_endpoint(
        payload=MessageCreate(workspace_id="ws-1", channel_id="ch-1", author_id="user-1", body="hello"),
        session=object(),
    )

    assert result.id == "msg-1"
    fake_gateway.broadcast.assert_awaited_once()


@pytest.mark.asyncio
async def test_event_worker_ignores_duplicates() -> None:
    worker = EventWorker()
    event = {"event_id": "evt-123", "event_type": "message.created"}

    first = await worker.process_event(event)
    second = await worker.process_event(event)

    assert first["processed"] is True
    assert second["duplicate"] is True
