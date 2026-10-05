from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events.registry import build_event_envelope
from app.core.outbox.models import OutboxEvent


async def emit_outbox_event(
    session: AsyncSession,
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict,
    organization_id: str | None = None,
    workspace_id: str | None = None,
    conversation_id: str | None = None,
    actor_user_id: str | None = None,
    sequence: int | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    event_version: int = 1,
) -> OutboxEvent:
    envelope = build_event_envelope(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload,
        organization_id=organization_id,
        workspace_id=workspace_id,
        conversation_id=conversation_id,
        actor_user_id=actor_user_id,
        sequence=sequence,
        correlation_id=correlation_id,
        causation_id=causation_id,
        event_version=event_version,
    )
    event = OutboxEvent(
        id=str(uuid4()),
        event_id=envelope["event_id"],
        event_type=event_type,
        event_version=event_version,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        organization_id=organization_id,
        workspace_id=workspace_id,
        conversation_id=conversation_id,
        actor_user_id=actor_user_id,
        correlation_id=envelope["correlation_id"],
        causation_id=envelope["causation_id"],
        occurred_at=datetime.now(timezone.utc),
        payload=payload,
        created_at=datetime.now(timezone.utc),
        available_at=datetime.now(timezone.utc),
    )
    session.add(event)
    if hasattr(session, "flush"):
        await session.flush()
    return event
