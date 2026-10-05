from __future__ import annotations

from typing import Any


class EventDeduplicator:
    def __init__(self, max_size: int = 5000) -> None:
        self._seen: dict[str, int] = {}
        self.max_size = max_size

    def is_duplicate(self, event_id: str) -> bool:
        if event_id in self._seen:
            return True
        self._seen[event_id] = 1
        if len(self._seen) > self.max_size:
            for key in list(self._seen)[: len(self._seen) - self.max_size]:
                self._seen.pop(key, None)
        return False


class RealtimeConsumer:
    def __init__(self) -> None:
        self._deduplicator = EventDeduplicator()

    async def handle(self, event: dict[str, Any]) -> dict[str, Any]:
        event_id = str(event.get("event_id") or "unknown")
        if self._deduplicator.is_duplicate(event_id):
            return {"processed": True, "duplicate": True, "event_id": event_id}
        return {"processed": True, "duplicate": False, "event_id": event_id, "event_type": event.get("event_type")}
