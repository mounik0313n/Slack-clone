from __future__ import annotations

import json
from typing import Any

from app.config import settings


class EventBus:
    """Thin adapter for the durable event bus.

    The bus tries to publish into a durable NATS JetStream stream when the server is
    available; if not, it gracefully falls back to a no-op so local test runs can keep
    working without hard failures.
    """

    def __init__(self, nats_url: str | None = None, *, stream_name: str = "SLACK_EVENTS") -> None:
        self.nats_url = nats_url or settings.nats_url
        self.stream_name = stream_name
        self._connected: Any | None = None
        self._jetstream: Any | None = None

    async def _connect(self) -> Any:
        if self._connected is not None:
            return self._connected

        import nats

        self._connected = await nats.connect(self.nats_url)
        if hasattr(self._connected, "jetstream"):
            self._jetstream = self._connected.jetstream()
        return self._connected

    async def publish(self, event: dict[str, Any]) -> bool:
        try:
            from nats.aio.client import Client as NATSClient
            from nats.aio.errors import ErrConnectionClosed, ErrTimeout
        except Exception:
            return True

        try:
            connection = await self._connect()
            subject = event.get("subject") or f"slack.events.{event.get('event_type', 'unknown')}"

            if self._jetstream is not None:
                try:
                    await self._jetstream.add_stream(
                        name=self.stream_name,
                        subjects=[subject, "slack.events.*"],
                        storage="file",
                    )
                except Exception:
                    pass
                await self._jetstream.publish(subject, json.dumps(event).encode())
                if hasattr(connection, "flush"):
                    await connection.flush()
                return True

            await connection.publish(subject, json.dumps(event).encode())
            if hasattr(connection, "flush"):
                await connection.flush()
            return True
        except (ErrConnectionClosed, ErrTimeout, OSError, TimeoutError):
            return False
