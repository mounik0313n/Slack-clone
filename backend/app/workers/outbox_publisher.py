from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.core.events.bus import EventBus
from app.core.outbox.models import OutboxEvent


def _event_key(event: dict[str, Any]) -> str:
    return str(event.get("event_id") or event.get("id") or "unknown")


class OutboxPublisher:
    def __init__(self, *, stream_name: str = "SLACK_EVENTS", nats_url: str | None = None) -> None:
        self.stream_name = stream_name
        self.nats_url = nats_url
        self.bus = EventBus(nats_url=nats_url)
        self._seen_event_ids: set[str] = set()

    async def _record_seen(self, event: dict[str, Any]) -> bool:
        key = _event_key(event)
        if key in self._seen_event_ids:
            return False
        self._seen_event_ids.add(key)
        return True

    async def publish_pending(self, session: Any) -> list[dict[str, Any]]:
        if not hasattr(session, "execute"):
            return []

        result = await session.execute(
            select(OutboxEvent).where(
                OutboxEvent.published_at.is_(None),
                OutboxEvent.available_at <= datetime.now(timezone.utc),
            )
            .order_by(OutboxEvent.created_at.asc())
        )
        rows = list(result.scalars().all())
        published: list[dict[str, Any]] = []
        for row in rows:
            event = {
                "event_id": row.event_id,
                "event_type": row.event_type,
                "event_version": row.event_version,
                "aggregate_type": row.aggregate_type,
                "aggregate_id": row.aggregate_id,
                "organization_id": row.organization_id,
                "workspace_id": row.workspace_id,
                "conversation_id": row.conversation_id,
                "actor_user_id": row.actor_user_id,
                "payload": row.payload,
                "occurred_at": row.occurred_at.isoformat() if row.occurred_at else datetime.now(timezone.utc).isoformat(),
                "subject": f"slack.events.{row.event_type.replace('.', '.')}" if row.event_type else "slack.events.unknown",
            }
            if not await self._record_seen(event):
                continue
            try:
                published_event = await self.bus.publish(event)
                if published_event:
                    row.published_at = datetime.now(timezone.utc)
                    row.processed_at = row.published_at
                    row.retry_count = max(0, row.retry_count)
                    published.append(event)
                else:
                    row.retry_count = int(row.retry_count or 0) + 1
                    row.available_at = datetime.now(timezone.utc) + timedelta(seconds=min(60, 2 ** min(row.retry_count, 6)))
                    row.last_error = "nats_publish_failed"
            except Exception as exc:  # pragma: no cover - defensive path for runtime recovery
                row.retry_count = int(row.retry_count or 0) + 1
                row.last_error = str(exc)
                row.available_at = datetime.now(timezone.utc) + timedelta(seconds=min(60, 2 ** min(row.retry_count, 6)))
        if rows:
            await session.commit()
        return published
