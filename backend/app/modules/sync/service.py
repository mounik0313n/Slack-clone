from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.conversations.models import Conversation, ConversationMember
from app.modules.messages.models import Message
from app.modules.notifications.models import Notification
from app.modules.read_states.models import ReadState


def _to_serializable(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _safe_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return int(cursor.split(":")[-1])
    except (TypeError, ValueError):
        return 0


def build_sync_token(*, user_id: str, workspace_id: str, cursor: str | None, count: int) -> str:
    stamp = f"{user_id}:{workspace_id}:{cursor or '0'}:{count}:{int(datetime.now(timezone.utc).timestamp())}"
    return hashlib.sha256(stamp.encode("utf-8")).hexdigest()[:24]


async def collect_sync_snapshot(
    session: AsyncSession,
    *,
    user_id: str,
    workspace_id: str,
    conversation_ids: list[str] | None = None,
    cursor: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    if not hasattr(session, "execute"):
        return {
            "type": "sync.response",
            "sync_version": 1,
            "sync_token": build_sync_token(user_id=user_id, workspace_id=workspace_id, cursor=cursor, count=0),
            "conversations": [],
            "messages": [],
            "read_states": [],
            "notifications": [],
            "next_cursor": cursor,
        }

    if conversation_ids:
        requested_conversations = list(dict.fromkeys(conversation_ids))
    else:
        member_rows = await session.execute(
            select(ConversationMember.conversation_id).where(
                ConversationMember.user_id == user_id,
            )
        )
        requested_conversations = [row[0] for row in member_rows.all()]

    if requested_conversations:
        result = await session.execute(
            select(Conversation).where(
                Conversation.id.in_(requested_conversations),
                Conversation.workspace_id == workspace_id,
            )
        )
        conversations = list(result.scalars().all())
    else:
        conversations = []

    message_query = select(Message).where(
        Message.workspace_id == workspace_id,
    )
    if requested_conversations:
        message_query = message_query.where(Message.channel_id.in_(requested_conversations))
    if cursor:
        message_query = message_query.where(Message.sequence > _safe_cursor(cursor))
    message_query = message_query.order_by(Message.sequence.asc()).limit(limit)
    message_result = await session.execute(message_query)
    messages = [
        {
            "id": message.id,
            "workspace_id": message.workspace_id,
            "channel_id": message.channel_id,
            "author_id": message.author_id,
            "sequence": message.sequence,
            "body": message.body,
            "thread_id": getattr(message, "thread_id", None),
            "client_message_id": getattr(message, "client_message_id", None),
            "created_at": _to_serializable(getattr(message, "created_at", datetime.now(timezone.utc))),
            "updated_at": _to_serializable(getattr(message, "updated_at", None)),
        }
        for message in message_result.scalars().all()
    ]

    read_query = select(ReadState).where(
        ReadState.workspace_id == workspace_id,
        ReadState.user_id == user_id,
    )
    if requested_conversations:
        read_query = read_query.where(ReadState.channel_id.in_(requested_conversations))
    read_result = await session.execute(read_query)
    read_states = [
        {
            "id": getattr(state, "id", None),
            "workspace_id": getattr(state, "workspace_id", workspace_id),
            "channel_id": getattr(state, "channel_id", None),
            "user_id": getattr(state, "user_id", user_id),
            "last_read_sequence": getattr(state, "last_read_sequence", 0),
            "last_read_message_id": getattr(state, "last_read_message_id", None),
            "updated_at": _to_serializable(getattr(state, "updated_at", None)),
        }
        for state in read_result.scalars().all()
    ]

    notification_query = select(Notification).where(
        Notification.recipient_user_id == user_id,
        Notification.workspace_id == workspace_id,
    )
    if requested_conversations:
        notification_query = notification_query.where(Notification.conversation_id.in_(requested_conversations))
    notification_result = await session.execute(
        notification_query.order_by(Notification.created_at.desc()).limit(limit)
    )
    notifications = [
        {
            "id": getattr(notification, "id", None),
            "workspace_id": getattr(notification, "workspace_id", workspace_id),
            "recipient_user_id": getattr(notification, "recipient_user_id", user_id),
            "actor_user_id": getattr(notification, "actor_user_id", None),
            "type": getattr(notification, "type", "UNKNOWN"),
            "conversation_id": getattr(notification, "conversation_id", None),
            "message_id": getattr(notification, "message_id", None),
            "thread_id": getattr(notification, "thread_id", None),
            "payload": getattr(notification, "payload", None),
            "read_at": _to_serializable(getattr(notification, "read_at", None)),
            "created_at": _to_serializable(getattr(notification, "created_at", datetime.now(timezone.utc))),
        }
        for notification in notification_result.scalars().all()
    ]

    next_cursor = str(max((message["sequence"] for message in messages), default=_safe_cursor(cursor))) if messages else cursor or "0"
    payload = {
        "type": "sync.response",
        "sync_version": 1,
        "sync_token": build_sync_token(user_id=user_id, workspace_id=workspace_id, cursor=next_cursor, count=len(messages) + len(notifications)),
        "conversations": [
            {
                "id": getattr(conversation, "id", None),
                "workspace_id": getattr(conversation, "workspace_id", workspace_id),
                "type": getattr(conversation, "type", "channel"),
                "name": getattr(conversation, "name", None),
                "created_by": getattr(conversation, "created_by", user_id),
                "channel_id": getattr(conversation, "channel_id", None),
                "created_at": _to_serializable(getattr(conversation, "created_at", datetime.now(timezone.utc))),
            }
            for conversation in conversations
        ],
        "messages": messages,
        "read_states": read_states,
        "notifications": notifications,
        "next_cursor": next_cursor,
        "sync_required": False,
    }
    return payload
