from __future__ import annotations

from typing import Any


class NotificationConsumer:
    def __init__(self) -> None:
        self.processed_event_ids: set[str] = set()

    async def handle(self, event: dict[str, Any]) -> dict[str, Any]:
        event_id = str(event.get("event_id") or "unknown")
        if event_id in self.processed_event_ids:
            return {"processed": True, "duplicate": True, "event_id": event_id}
        self.processed_event_ids.add(event_id)
        return {"processed": True, "duplicate": False, "event_id": event_id, "event_type": event.get("event_type")}
