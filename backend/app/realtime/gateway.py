from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import WebSocket


class RealtimeGateway:
    def __init__(self) -> None:
        self.connections: dict[str, WebSocket] = {}
        self.subscriptions: dict[str, set[str]] = {}
        self.channel_history: dict[str, deque[dict]] = defaultdict(lambda: deque(maxlen=200))
        self.user_devices: dict[str, set[str]] = defaultdict(set)
        self.client_users: dict[str, str] = {}
        self.last_seen: dict[str, datetime] = {}

    async def connect(self, websocket: WebSocket, client_id: str, user_id: str | None = None) -> None:
        if hasattr(websocket, "accept"):
            await websocket.accept()
        self.connections[client_id] = websocket
        self.subscriptions.setdefault(client_id, set())
        self.last_seen[client_id] = datetime.now(timezone.utc)
        if user_id:
            self.client_users[client_id] = user_id
            self.user_devices[user_id].add(client_id)

    def disconnect(self, client_id: str) -> None:
        self.connections.pop(client_id, None)
        self.subscriptions.pop(client_id, None)
        self.last_seen.pop(client_id, None)
        self.client_users.pop(client_id, None)
        for user_id, device_ids in list(self.user_devices.items()):
            device_ids.discard(client_id)
            if not device_ids:
                self.user_devices.pop(user_id, None)

    def subscribe(self, client_id: str, channel: str) -> None:
        self.subscriptions.setdefault(client_id, set()).add(channel)

    def unsubscribe(self, client_id: str, channel: str) -> None:
        self.subscriptions.get(client_id, set()).discard(channel)

    def build_event(
        self,
        *,
        event_type: str,
        payload: dict,
        organization_id: str | None = None,
        workspace_id: str | None = None,
        channel_id: str | None = None,
        sequence: int | None = None,
        client_id: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        return {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "event_version": 1,
            "organization_id": organization_id,
            "workspace_id": workspace_id or payload.get("workspace_id"),
            "conversation_id": channel_id or payload.get("channel_id"),
            "sequence": sequence if sequence is not None else payload.get("sequence"),
            "client_id": client_id or payload.get("client_id"),
            "user_id": user_id or payload.get("user_id") or self.client_users.get(client_id or ""),
            "actor_id": payload.get("actor_id"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }

    def _record_channel_event(self, channel: str | None, event: dict) -> None:
        if channel is None:
            return
        self.channel_history[channel].append(event)

    async def broadcast(
        self,
        event_type: str,
        payload: dict,
        *,
        channel: str | None = None,
        user_id: str | None = None,
        client_id: str | None = None,
    ) -> dict:
        message = self.build_event(
            event_type=event_type,
            payload=payload,
            workspace_id=payload.get("workspace_id"),
            channel_id=channel or payload.get("channel_id"),
            sequence=payload.get("sequence"),
            client_id=client_id or payload.get("client_id"),
            user_id=user_id or payload.get("user_id"),
        )
        self._record_channel_event(channel or payload.get("channel_id"), message)

        if channel is not None:
            targets = [
                cid for cid, channels in self.subscriptions.items() if channel in channels
            ]
        elif user_id is not None:
            targets = list(self.user_devices.get(user_id, set()))
        else:
            targets = list(self.connections)

        if client_id is not None:
            targets = list(dict.fromkeys([client_id, *targets]))

        for target in targets:
            websocket = self.connections.get(target)
            if websocket is not None:
                await websocket.send_json(message)
        return message

    async def resume(self, client_id: str, channels: list[str] | None = None) -> list[dict]:
        websocket = self.connections.get(client_id)
        if websocket is None:
            return []

        requested = channels or list(self.subscriptions.get(client_id, set()))
        history: list[dict] = []
        for channel in requested:
            for event in list(self.channel_history.get(channel, deque())):
                await websocket.send_json(event)
                history.append(event)
        return history

    async def replay(self, client_id: str, channels: list[str] | None = None) -> list[dict]:
        return await self.resume(client_id, channels)

    def prune_stale_connections(self, *, max_idle_seconds: float = 120.0) -> list[str]:
        now = datetime.now(timezone.utc)
        stale_clients = [
            client_id
            for client_id, seen_at in self.last_seen.items()
            if (now - seen_at).total_seconds() > max_idle_seconds
        ]

        for client_id in stale_clients:
            self.disconnect(client_id)

        return stale_clients

    async def heartbeat(self, client_id: str | None = None, *, sync_required: bool = False) -> dict:
        ts = datetime.now(timezone.utc).isoformat()
        event = {
            "event_id": str(uuid4()),
            "event_type": "heartbeat",
            "event_version": 1,
            "payload": {
                "timestamp": ts,
                "client_id": client_id,
                "sync_required": bool(sync_required),
            },
        }

        if client_id is not None:
            websocket = self.connections.get(client_id)
            if websocket is not None:
                await websocket.send_json(event)
            self.last_seen[client_id] = datetime.now(timezone.utc)
            return event

        for target, websocket in list(self.connections.items()):
            event["payload"] = {"timestamp": ts, "client_id": target, "sync_required": bool(sync_required)}
            await websocket.send_json(event)
            self.last_seen[target] = datetime.now(timezone.utc)
        return event
