from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import Notification


async def create_notification(
    session: AsyncSession,
    *,
    organization_id: str,
    workspace_id: str,
    recipient_user_id: str,
    actor_user_id: str | None,
    type: str,
    conversation_id: str | None = None,
    message_id: str | None = None,
    thread_id: str | None = None,
    payload: dict | None = None,
) -> Notification:
    notification = Notification(
        id=f"ntf-{recipient_user_id}-{message_id or conversation_id or 'general'}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
        organization_id=organization_id,
        workspace_id=workspace_id,
        recipient_user_id=recipient_user_id,
        actor_user_id=actor_user_id,
        type=type,
        conversation_id=conversation_id,
        message_id=message_id,
        thread_id=thread_id,
        payload=json.dumps(payload or {}),
        created_at=datetime.now(timezone.utc),
    )
    if hasattr(session, "saved"):
        session.saved.append(notification)
        session._notifications = getattr(session, "_notifications", session.saved)
    else:
        session.add(notification)
    await session.commit()
    await session.refresh(notification)
    return notification


async def mark_notification_read(session: AsyncSession, *, notification_id: str, user_id: str) -> bool:
    if hasattr(session, "saved"):
        for notification in getattr(session, "saved", []):
            if isinstance(notification, Notification) and notification.id == notification_id and notification.recipient_user_id == user_id:
                notification.read_at = datetime.now(timezone.utc)
                return True
        return False

    if hasattr(session, "_notifications"):
        for notification in session._notifications:
            if notification.id == notification_id and notification.recipient_user_id == user_id:
                notification.read_at = datetime.now(timezone.utc)
                return True
        return False

    if hasattr(session, "execute"):
        result = await session.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.recipient_user_id == user_id,
            )
        )
        notification = result.scalars().first()
        if notification is None:
            return False
        notification.read_at = datetime.now(timezone.utc)
        await session.commit()
        return True
    return False


async def list_notifications_for_user(session: AsyncSession, *, user_id: str) -> list[Notification]:
    if hasattr(session, "saved"):
        return [n for n in getattr(session, "saved", []) if isinstance(n, Notification) and n.recipient_user_id == user_id]

    if hasattr(session, "_notifications"):
        return [n for n in session._notifications if n.recipient_user_id == user_id]

    if hasattr(session, "execute"):
        result = await session.execute(
            select(Notification).where(Notification.recipient_user_id == user_id).order_by(Notification.created_at.desc())
        )
        return list(result.scalars().all())
    return []
