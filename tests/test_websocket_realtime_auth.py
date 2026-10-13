from __future__ import annotations

import pytest

from app.config import create_token
from app.modules.auth.service import revoke_token
from app.realtime.gateway import RealtimeGateway


class MockWebSocket:
    def __init__(self) -> None:
        self.sent_messages = []
        self.closed = False

    async def send_json(self, data):
        self.sent_messages.append(data)

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_realtime_gateway_subscription_and_broadcast() -> None:
    gateway = RealtimeGateway()
    ws1 = MockWebSocket()
    ws2 = MockWebSocket()

    await gateway.connect(ws1, "client-1")
    await gateway.connect(ws2, "client-2")

    # Subscribe client 1 to channel-A, client 2 to channel-B
    gateway.subscribe("client-1", "channel-A")
    gateway.subscribe("client-2", "channel-B")

    # Broadcast on channel-A
    await gateway.broadcast("message.created", {"text": "hello channel A"}, channel="channel-A")

    # Client 1 should receive event, Client 2 should not
    assert len(ws1.sent_messages) == 1
    assert ws1.sent_messages[0]["event_type"] == "message.created"
    assert ws1.sent_messages[0]["payload"]["text"] == "hello channel A"
    assert len(ws2.sent_messages) == 0

    # Unsubscribe client 1
    gateway.unsubscribe("client-1", "channel-A")
    await gateway.broadcast("message.created", {"text": "hello again"}, channel="channel-A")
    assert len(ws1.sent_messages) == 1  # No new message

    gateway.disconnect("client-1")
    gateway.disconnect("client-2")


def test_token_creation_and_revocation_for_realtime() -> None:
    token = create_token("user-rt-1", token_type="access", email="rt@example.com")
    assert isinstance(token, str)

    revoke_token(token)
    from app.modules.auth.service import is_token_revoked
    assert is_token_revoked(token) is True
