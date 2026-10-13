from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db, get_optional_current_user
from app.modules.messages.schemas import MessageCreate, MessageRead
from app.modules.messages.service import create_message, list_messages

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("", response_model=list[MessageRead])
async def get_messages(
    channel_id: str | None = None,
    thread_id: str | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[MessageRead]:
    messages = await list_messages(session, channel_id=channel_id, thread_id=thread_id)
    return [
        MessageRead(
            id=message.id,
            workspace_id=message.workspace_id,
            channel_id=message.channel_id,
            author_id=message.author_id,
            sequence=message.sequence,
            body=message.body,
            thread_id=message.thread_id,
            client_message_id=message.client_message_id,
            created_at=message.created_at,
            updated_at=message.updated_at,
        )
        for message in messages
    ]


@router.post("", response_model=MessageRead, status_code=201)
async def create_message_endpoint(
    payload: MessageCreate,
    session: AsyncSession = Depends(get_db),
    current_user: dict | None = Depends(get_optional_current_user),
) -> MessageRead:
    user_authenticated = isinstance(current_user, dict)
    if settings.app_env.lower() == "production" and not user_authenticated:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    # Secure actor resolution: server context overrides client-supplied author_id
    author_id = current_user["user_id"] if user_authenticated else payload.author_id

    message = await create_message(
        session,
        workspace_id=payload.workspace_id,
        channel_id=payload.channel_id,
        author_id=author_id,
        body=payload.body,
        thread_id=payload.thread_id,
        client_message_id=payload.client_message_id,
    )

    from app.main import realtime_gateway

    await realtime_gateway.broadcast(
        "message.created",
        {
            "message_id": message.id,
            "workspace_id": message.workspace_id,
            "channel_id": message.channel_id,
            "author_id": message.author_id,
            "body": message.body,
            "thread_id": message.thread_id,
            "sequence": message.sequence,
            "client_message_id": getattr(message, "client_message_id", None),
        },
        channel=message.channel_id,
    )

    return MessageRead(
        id=message.id,
        workspace_id=message.workspace_id,
        channel_id=message.channel_id,
        author_id=message.author_id,
        sequence=message.sequence,
        body=message.body,
        thread_id=message.thread_id,
        client_message_id=getattr(message, "client_message_id", None),
        created_at=message.created_at or datetime.now(timezone.utc),
        updated_at=message.updated_at,
    )
