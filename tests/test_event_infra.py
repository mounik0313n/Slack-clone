from __future__ import annotations

import sys
import types
from datetime import datetime, timedelta, timezone

import pytest

from app.core.events.registry import build_event_envelope
from app.core.outbox.service import emit_outbox_event
from app.modules.devices.service import register_device, revoke_device
from app.modules.sync.service import collect_sync_snapshot
from app.realtime.gateway import RealtimeGateway
from app.workers.outbox_publisher import OutboxPublisher, _event_key


@pytest.mark.asyncio
async def test_event_envelope_has_required_metadata() -> None:
    envelope = build_event_envelope(
        event_type='message.created',
        aggregate_type='message',
        aggregate_id='msg-1',
        organization_id='org-1',
        workspace_id='ws-1',
        conversation_id='ch-1',
        actor_user_id='user-1',
        payload={'body': 'hello'},
    )

    assert envelope['event_type'] == 'message.created'
    assert envelope['event_version'] == 1
    assert envelope['workspace_id'] == 'ws-1'
    assert envelope['conversation_id'] == 'ch-1'
    assert envelope['payload']['body'] == 'hello'


@pytest.mark.asyncio
async def test_emit_outbox_event_tracks_event_metadata() -> None:
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
        event_type='notification.created',
        aggregate_type='notification',
        aggregate_id='ntf-1',
        organization_id='org-1',
        workspace_id='ws-1',
        conversation_id='ch-1',
        actor_user_id='user-2',
        payload={'recipient_user_id': 'user-1'},
    )

    assert event.event_id.startswith('evt-')
    assert event.event_type == 'notification.created'
    assert event.workspace_id == 'ws-1'
    assert event.conversation_id == 'ch-1'
    assert event.actor_user_id == 'user-2'


@pytest.mark.asyncio
async def test_outbox_publisher_deduplicates_events_by_key() -> None:
    event = {
        'event_id': 'evt-123',
        'event_type': 'message.created',
        'workspace_id': 'ws-1',
        'conversation_id': 'ch-1',
        'payload': {'body': 'hello'},
        'occurred_at': datetime.now(timezone.utc).isoformat(),
    }
    assert _event_key(event) == 'evt-123'

    publisher = OutboxPublisher()
    publisher._seen_event_ids.clear()
    assert await publisher._record_seen(event) is True
    assert await publisher._record_seen(event) is False


@pytest.mark.asyncio
async def test_event_bus_uses_jetstream_when_available(monkeypatch) -> None:
    calls: dict[str, object] = {}

    class FakeJS:
        def __init__(self) -> None:
            self.streams: list[dict[str, object]] = []

        async def add_stream(self, **kwargs: object) -> dict[str, object]:
            self.streams.append(kwargs)
            calls['stream'] = kwargs
            return kwargs

        async def publish(self, subject: str, payload: bytes) -> object:
            calls['publish'] = (subject, payload)
            return object()

    class FakeNATSClient:
        def __init__(self) -> None:
            self.js = FakeJS()

        def jetstream(self) -> FakeJS:
            return self.js

        async def flush(self) -> None:
            return None

    async def fake_connect(url: str) -> FakeNATSClient:
        calls['url'] = url
        return FakeNATSClient()

    nats_module = types.ModuleType('nats')
    nats_module.connect = fake_connect
    aio_module = types.ModuleType('nats.aio')
    client_module = types.ModuleType('nats.aio.client')
    client_module.Client = FakeNATSClient
    errors_module = types.ModuleType('nats.aio.errors')
    errors_module.ErrConnectionClosed = RuntimeError
    errors_module.ErrTimeout = TimeoutError

    monkeypatch.setitem(sys.modules, 'nats', nats_module)
    monkeypatch.setitem(sys.modules, 'nats.aio', aio_module)
    monkeypatch.setitem(sys.modules, 'nats.aio.client', client_module)
    monkeypatch.setitem(sys.modules, 'nats.aio.errors', errors_module)

    from app.core.events.bus import EventBus

    bus = EventBus(nats_url='nats://example:4222')
    result = await bus.publish({
        'event_type': 'message.created',
        'subject': 'slack.events.message.created',
        'payload': {'body': 'hello'},
    })

    assert result is True
    assert calls['url'] == 'nats://example:4222'
    assert calls['stream']['name'] == 'SLACK_EVENTS'
    assert calls['publish'][0] == 'slack.events.message.created'


@pytest.mark.asyncio
async def test_realtime_gateway_supports_resume_replay_and_heartbeat() -> None:
    class FakeSocket:
        def __init__(self) -> None:
            self.sent: list[dict[str, object]] = []

        async def send_json(self, payload: dict[str, object]) -> None:
            self.sent.append(payload)

    gateway = RealtimeGateway()
    socket = FakeSocket()
    await gateway.connect(socket, 'device-1')
    gateway.subscribe('device-1', 'general')

    await gateway.broadcast(
        'message.created',
        {'workspace_id': 'ws-1', 'channel_id': 'general', 'body': 'hello'},
        channel='general',
    )

    replay = await gateway.resume('device-1', ['general'])
    assert replay
    assert replay[0]['payload']['body'] == 'hello'

    await gateway.heartbeat('device-1')
    assert socket.sent[-1]['event_type'] == 'heartbeat'


@pytest.mark.asyncio
async def test_collect_sync_snapshot_returns_authoritative_state() -> None:
    class FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def scalars(self):
            return self

        def all(self):
            return list(self._rows)

        def first(self):
            return self._rows[0] if self._rows else None

    class FakeSession:
        def __init__(self):
            self._messages = [
                type('Message', (), {'workspace_id': 'ws-1', 'channel_id': 'general', 'sequence': 101, 'body': 'hello', 'author_id': 'user-1', 'id': 'msg-1', 'created_at': datetime.now(timezone.utc)})(),
                type('Message', (), {'workspace_id': 'ws-1', 'channel_id': 'general', 'sequence': 102, 'body': 'hi', 'author_id': 'user-2', 'id': 'msg-2', 'created_at': datetime.now(timezone.utc)})(),
            ]
            self._read_states = [
                type('ReadState', (), {'workspace_id': 'ws-1', 'channel_id': 'general', 'user_id': 'user-1', 'last_read_sequence': 100, 'last_read_message_id': 'msg-1', 'updated_at': datetime.now(timezone.utc)})(),
            ]
            self._notifications = [
                type('Notification', (), {'workspace_id': 'ws-1', 'recipient_user_id': 'user-1', 'type': 'MENTION', 'conversation_id': 'general', 'message_id': 'msg-2', 'payload': '{"body":"hi"}', 'read_at': None, 'created_at': datetime.now(timezone.utc)})(),
            ]
            self._conversations = [
                type('Conversation', (), {'id': 'conv-general', 'workspace_id': 'ws-1', 'type': 'channel', 'name': 'general', 'created_by': 'user-1', 'channel_id': 'general'})(),
            ]

        async def execute(self, query):
            return FakeResult(self._messages if 'messages' in str(query).lower() else self._read_states if 'read_states' in str(query).lower() else self._notifications if 'notifications' in str(query).lower() else self._conversations)

    snapshot = await collect_sync_snapshot(FakeSession(), user_id='user-1', workspace_id='ws-1', conversation_ids=['general'])
    assert snapshot['sync_version'] == 1
    assert snapshot['messages'][0]['sequence'] == 101
    assert snapshot['read_states'][0]['channel_id'] == 'general'
    assert snapshot['notifications'][0]['type'] == 'MENTION'


@pytest.mark.asyncio
async def test_device_registration_and_revocation() -> None:
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
    device = await register_device(
        session,
        user_id='user-1',
        device_identifier='device-abc',
        platform='web',
        browser='chrome',
        session_token='session-1',
    )

    assert device.device_identifier == 'device-abc'
    assert device.revoked_at is None

    revoked = await revoke_device(session, device_id=device.id, user_id='user-1')
    assert revoked is True
    assert device.revoked_at is not None


@pytest.mark.asyncio
async def test_realtime_gateway_prunes_stale_connections_and_tracks_heartbeat() -> None:
    class FakeSocket:
        def __init__(self) -> None:
            self.sent: list[dict[str, object]] = []

        async def send_json(self, payload: dict[str, object]) -> None:
            self.sent.append(payload)

    gateway = RealtimeGateway()
    socket = FakeSocket()
    await gateway.connect(socket, 'device-2')

    gateway.last_seen['device-2'] = datetime.now(timezone.utc) - timedelta(seconds=5)
    stale = gateway.prune_stale_connections(max_idle_seconds=0.01)
    assert 'device-2' in stale
    assert 'device-2' not in gateway.connections

    gateway.last_seen['device-2'] = datetime.now(timezone.utc)
    heartbeat = await gateway.heartbeat('device-2', sync_required=True)
    assert heartbeat['event_type'] == 'heartbeat'
    assert heartbeat['payload']['sync_required'] is True
