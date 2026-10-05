from __future__ import annotations

import asyncio
from typing import Any


class EventWorker:
    def __init__(self, stream_name: str = "DOMAIN_EVENTS") -> None:
        self.stream_name = stream_name
        self.running = False
        self.processed_events: set[str] = set()

    async def start(self) -> None:
        self.running = True
        while self.running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        self.running = False

    async def process_event(self, event: dict[str, Any]) -> dict[str, Any]:
        event_id = str(event.get("event_id") or event.get("id") or "unknown")
        if event_id in self.processed_events:
            return {"processed": True, "duplicate": True, "event_id": event_id}
        self.processed_events.add(event_id)
        return {"processed": True, "duplicate": False, "event_type": event.get("event_type"), "event_id": event_id}
