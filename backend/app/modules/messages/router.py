from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.authorization import require_permission
from app.core.tenancy.context import ensure_tenant_boundaries
from app.dependencies import get_current_user, get_db
from app.modules.channels.models import Channel, ChannelMember
from app.modules.messages.schemas import MessageCreate, MessageRead, MessageUpdate
from app.modules.messages.service import (
    create_message,
    delete_message,
    list_messages,
    list_pinned_messages,
    toggle_pin_message,
    update_message,
)

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("", response_model=list[MessageRead])
async def get_messages(
    channel_id: str | None = None,
    thread_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    before_sequence: int | None = Query(default=None),
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

    messages = await list_messages(
        session,
        channel_id=channel_id,
        thread_id=thread_id,
        limit=limit,
        before_sequence=before_sequence,
    )
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
            is_pinned=getattr(message, "is_pinned", False),
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
        is_pinned=getattr(message, "is_pinned", False),
        created_at=message.created_at,
        updated_at=message.updated_at,
    )


@router.patch("/{message_id}", response_model=MessageRead)
async def update_message_endpoint(
    message_id: str,
    payload: MessageUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> MessageRead:
    require_permission(current_user, "message.create")
    is_admin = current_user.get("role") == "admin"
    try:
        updated = await update_message(
            session,
            message_id=message_id,
            body=payload.body,
            actor_id=current_user["user_id"],
            is_admin=is_admin,
        )
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot edit another user's message")

    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    try:
        from app.main import realtime_gateway
        await realtime_gateway.broadcast(
            "message.updated",
            {
                "message_id": updated.id,
                "workspace_id": updated.workspace_id,
                "channel_id": updated.channel_id,
                "author_id": updated.author_id,
                "body": updated.body,
                "is_pinned": getattr(updated, "is_pinned", False),
                "updated_at": updated.updated_at.isoformat() if updated.updated_at else None,
            },
            channel=updated.channel_id,
        )
    except Exception:
        pass

    return MessageRead(
        id=updated.id,
        workspace_id=updated.workspace_id,
        channel_id=updated.channel_id,
        author_id=updated.author_id,
        sequence=updated.sequence,
        body=updated.body,
        thread_id=updated.thread_id,
        client_message_id=updated.client_message_id,
        is_pinned=getattr(updated, "is_pinned", False),
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    )


@router.post("/{message_id}/pin", response_model=MessageRead)
async def pin_message_endpoint(
    message_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> MessageRead:
    require_permission(current_user, "message.create")
    pinned = await toggle_pin_message(session, message_id=message_id, pin=True)
    if not pinned:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    try:
        from app.main import realtime_gateway
        await realtime_gateway.broadcast(
            "message.pinned",
            {
                "message_id": pinned.id,
                "workspace_id": pinned.workspace_id,
                "channel_id": pinned.channel_id,
                "is_pinned": True,
            },
            channel=pinned.channel_id,
        )
    except Exception:
        pass

    return MessageRead(
        id=pinned.id,
        workspace_id=pinned.workspace_id,
        channel_id=pinned.channel_id,
        author_id=pinned.author_id,
        sequence=pinned.sequence,
        body=pinned.body,
        thread_id=pinned.thread_id,
        client_message_id=pinned.client_message_id,
        is_pinned=pinned.is_pinned,
        created_at=pinned.created_at,
        updated_at=pinned.updated_at,
    )


@router.delete("/{message_id}/pin", response_model=MessageRead)
async def unpin_message_endpoint(
    message_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> MessageRead:
    require_permission(current_user, "message.create")
    unpinned = await toggle_pin_message(session, message_id=message_id, pin=False)
    if not unpinned:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    try:
        from app.main import realtime_gateway
        await realtime_gateway.broadcast(
            "message.unpinned",
            {
                "message_id": unpinned.id,
                "workspace_id": unpinned.workspace_id,
                "channel_id": unpinned.channel_id,
                "is_pinned": False,
            },
            channel=unpinned.channel_id,
        )
    except Exception:
        pass

    return MessageRead(
        id=unpinned.id,
        workspace_id=unpinned.workspace_id,
        channel_id=unpinned.channel_id,
        author_id=unpinned.author_id,
        sequence=unpinned.sequence,
        body=unpinned.body,
        thread_id=unpinned.thread_id,
        client_message_id=unpinned.client_message_id,
        is_pinned=unpinned.is_pinned,
        created_at=unpinned.created_at,
        updated_at=unpinned.updated_at,
    )


@router.get("/pinned/channel/{channel_id}", response_model=list[MessageRead])
async def get_pinned_messages_endpoint(
    channel_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> list[MessageRead]:
    require_permission(current_user, "message.read")
    messages = await list_pinned_messages(session, channel_id=channel_id)
    return [
        MessageRead(
            id=m.id,
            workspace_id=m.workspace_id,
            channel_id=m.channel_id,
            author_id=m.author_id,
            sequence=m.sequence,
            body=m.body,
            thread_id=m.thread_id,
            client_message_id=m.client_message_id,
            is_pinned=m.is_pinned,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
        for m in messages
    ]


@router.delete("/{message_id}")
async def delete_message_endpoint(
    message_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, str | bool]:
    require_permission(current_user, "message.create")
    is_admin = current_user.get("role") == "admin"
    try:
        deleted = await delete_message(
            session,
            message_id=message_id,
            actor_id=current_user["user_id"],
            is_admin=is_admin,
        )
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete another user's message")

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    try:
        from app.main import realtime_gateway
        await realtime_gateway.broadcast(
            "message.deleted",
            {
                "message_id": deleted.id,
                "workspace_id": deleted.workspace_id,
                "channel_id": deleted.channel_id,
            },
            channel=deleted.channel_id,
        )
    except Exception:
        pass

    return {"status": "ok", "deleted": True, "message_id": message_id}

