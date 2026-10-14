from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.authorization import require_permission
from app.core.tenancy.context import ensure_tenant_boundaries
from app.dependencies import get_current_user, get_db
from app.modules.channels.models import Channel, ChannelMember
from app.modules.messages.schemas import MessageCreate, MessageRead
from app.modules.messages.service import create_message, list_messages

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("", response_model=list[MessageRead])
async def get_messages(
    channel_id: str | None = None,
    thread_id: str | None = None,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> list[MessageRead]:
    if isinstance(current_user, dict):
        require_permission(current_user, "message.read")

        # If channel_id specified, enforce channel access boundaries
        if channel_id and hasattr(session, "get"):
            channel = await session.get(Channel, channel_id)
            if not channel:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
            ensure_tenant_boundaries(current_user, workspace_id=channel.workspace_id)

            if channel.is_private:
                is_member = await session.scalar(
                    select(ChannelMember).where(
                        ChannelMember.channel_id == channel_id,
                        ChannelMember.user_id == current_user["user_id"],
                    )
                )
                if not is_member and current_user.get("role") != "admin":
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to private channel")

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
    current_user: dict = Depends(get_current_user),
) -> MessageRead:
    if isinstance(current_user, dict):
        require_permission(current_user, "message.create")
        ensure_tenant_boundaries(current_user, workspace_id=payload.workspace_id)
        author_id = current_user["user_id"]
    else:
        author_id = payload.author_id

    # Verify channel boundaries if targeting a channel
    if payload.channel_id and hasattr(session, "get"):
        channel = await session.get(Channel, payload.channel_id)
        if not channel or channel.workspace_id != payload.workspace_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target channel not found in workspace")

        if channel.is_private:
            is_member = await session.scalar(
                select(ChannelMember).where(
                    ChannelMember.channel_id == payload.channel_id,
                    ChannelMember.user_id == author_id,
                )
            )
            role = current_user.get("role") if isinstance(current_user, dict) else "member"
            if not is_member and role != "admin":
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot send message to private channel without membership")

    message = await create_message(
        session,
        workspace_id=payload.workspace_id,
        channel_id=payload.channel_id,
        author_id=author_id,
        body=payload.body,
        thread_id=payload.thread_id,
        client_message_id=payload.client_message_id,
    )
    try:
        from app.main import realtime_gateway
        await realtime_gateway.broadcast(
            "message.created",
            {
                "message_id": message.id,
                "workspace_id": message.workspace_id,
                "channel_id": message.channel_id,
                "author_id": message.author_id,
                "sequence": message.sequence,
                "body": message.body,
                "thread_id": message.thread_id,
                "client_message_id": message.client_message_id,
                "created_at": message.created_at.isoformat(),
            },
            channel=message.channel_id,
        )
    except Exception:
        pass

    return MessageRead(
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
