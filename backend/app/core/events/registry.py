from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

EVENT_TYPES = {
    "conversation.created",
    "conversation.updated",
    "conversation.member_added",
    "conversation.member_removed",
    "conversation.archived",
    "conversation.unarchived",
    "message.created",
    "message.updated",
    "message.deleted",
    "thread.created",
    "thread.reply.created",
    "reaction.created",
    "reaction.deleted",
    "mention.created",
    "conversation.read",
    "thread.read",
    "notification.created",
    "notification.read",
    "presence.updated",
    "typing.started",
    "typing.stopped",
}


def build_event_envelope(
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
    organization_id: str | None = None,
    workspace_id: str | None = None,
    conversation_id: str | None = None,
    actor_user_id: str | None = None,
    sequence: int | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    occurred_at: datetime | None = None,
    event_version: int = 1,
) -> dict[str, Any]:
    if event_type not in EVENT_TYPES:
        # allow future event categories without breaking the registry
        EVENT_TYPES.add(event_type)

    occurred = occurred_at or datetime.now(timezone.utc)
    event_id = f"evt-{uuid4()}"
    return {
        "event_id": event_id,
        "event_type": event_type,
        "event_version": event_version,
        "organization_id": organization_id,
        "workspace_id": workspace_id,
        "conversation_id": conversation_id,
        "actor_user_id": actor_user_id,
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "occurred_at": occurred.isoformat(),
        "sequence": sequence,
        "correlation_id": correlation_id or event_id,
        "causation_id": causation_id or event_id,
        "payload": payload,
    }


def event_subject_for(event_type: str) -> str:
    cleaned = event_type.replace(".", ".")
    return f"slack.events.{cleaned}"
