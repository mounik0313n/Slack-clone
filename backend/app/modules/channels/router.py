from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.authorization import require_permission
from app.core.tenancy.context import ensure_tenant_boundaries
from app.dependencies import get_current_user, get_db
from app.modules.channels.models import Channel, ChannelMember
from app.modules.channels.schemas import (
    BookmarkCreate,
    BookmarkRead,
    ChannelCreate,
    ChannelMemberAdd,
    ChannelMemberRead,
    ChannelRead,
    ChannelUpdate,
)
from app.modules.channels.service import (
    add_channel_member,
    create_channel,
    create_channel_bookmark,
    delete_channel,
    delete_channel_bookmark,
    list_channel_bookmarks,
    list_channel_members,
    list_channels,
    remove_channel_member,
    update_channel,
)

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("", response_model=list[ChannelRead])
async def get_channels(
    workspace_id: str = Query("ws-default", description="Workspace ID"),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> list[ChannelRead]:
    require_permission(current_user, "channel.read")
    ensure_tenant_boundaries(current_user, workspace_id=workspace_id)

    if current_user.get("role") == "admin":
        query = select(Channel).where(Channel.workspace_id == workspace_id).order_by(Channel.created_at.desc())
    else:
        # Regular members see public channels + private channels they have joined
        user_channels_subquery = select(ChannelMember.channel_id).where(ChannelMember.user_id == current_user["user_id"])
        query = (
            select(Channel)
            .where(
                Channel.workspace_id == workspace_id,
                or_(
                    Channel.is_private == False,  # noqa: E712
                    Channel.id.in_(user_channels_subquery),
                ),
            )
            .order_by(Channel.created_at.desc())
        )

    result = await session.execute(query)
    channels = list(result.scalars().all())

    return [
        ChannelRead(
            id=channel.id,
            workspace_id=channel.workspace_id,
            name=channel.name,
            topic=channel.topic,
            is_private=channel.is_private,
            is_archived=channel.is_archived,
            created_at=channel.created_at,
        )
        for channel in channels
    ]


@router.post("", response_model=ChannelRead, status_code=201)
async def create_channel_endpoint(
    payload: ChannelCreate,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ChannelRead:
    require_permission(current_user, "channel.create")
    ensure_tenant_boundaries(current_user, workspace_id=payload.workspace_id)

    channel = await create_channel(
        session,
        workspace_id=payload.workspace_id,
        name=payload.name,
        topic=payload.topic,
        is_private=payload.is_private,
    )

    # If private channel, add creator as admin member
    if channel.is_private:
        member = ChannelMember(
            id=f"cm-{secrets.token_hex(8)}",
            channel_id=channel.id,
            user_id=current_user["user_id"],
            role="admin",
            joined_at=datetime.now(timezone.utc),
        )
        session.add(member)
        await session.commit()

    return ChannelRead(
        id=channel.id,
        workspace_id=channel.workspace_id,
        name=channel.name,
        topic=channel.topic,
        is_private=channel.is_private,
        is_archived=channel.is_archived,
        created_at=channel.created_at,
    )


@router.patch("/{channel_id}", response_model=ChannelRead)
async def update_channel_endpoint(
    channel_id: str,
    payload: ChannelUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ChannelRead:
    require_permission(current_user, "channel.create")
    channel = await session.get(Channel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    ensure_tenant_boundaries(current_user, workspace_id=channel.workspace_id)

    updated = await update_channel(
        session,
        channel_id=channel_id,
        name=payload.name,
        topic=payload.topic,
        is_archived=payload.is_archived,
    )
    return ChannelRead(
        id=updated.id,
        workspace_id=updated.workspace_id,
        name=updated.name,
        topic=updated.topic,
        is_private=updated.is_private,
        is_archived=updated.is_archived,
        created_at=updated.created_at,
    )


@router.delete("/{channel_id}")
async def delete_channel_endpoint(
    channel_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, str | bool]:
    require_permission(current_user, "workspace.manage")
    channel = await session.get(Channel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    ensure_tenant_boundaries(current_user, workspace_id=channel.workspace_id)

    await delete_channel(session, channel_id=channel_id)
    return {"status": "ok", "deleted": True, "channel_id": channel_id}


@router.get("/{channel_id}/members", response_model=list[ChannelMemberRead])
async def get_channel_members_endpoint(
    channel_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> list[ChannelMemberRead]:
    require_permission(current_user, "channel.read")
    channel = await session.get(Channel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    ensure_tenant_boundaries(current_user, workspace_id=channel.workspace_id)

    members = await list_channel_members(session, channel_id=channel_id)
    return [
        ChannelMemberRead(
            id=m.id,
            channel_id=m.channel_id,
            user_id=m.user_id,
            role=m.role,
            joined_at=m.joined_at,
        )
        for m in members
    ]


@router.post("/{channel_id}/members", response_model=ChannelMemberRead, status_code=201)
async def add_channel_member_endpoint(
    channel_id: str,
    payload: ChannelMemberAdd,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ChannelMemberRead:
    require_permission(current_user, "channel.create")
    channel = await session.get(Channel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    ensure_tenant_boundaries(current_user, workspace_id=channel.workspace_id)

    member = await add_channel_member(
        session,
        channel_id=channel_id,
        user_id=payload.user_id,
        role=payload.role,
    )
    return ChannelMemberRead(
        id=member.id,
        channel_id=member.channel_id,
        user_id=member.user_id,
        role=member.role,
        joined_at=member.joined_at,
    )


@router.delete("/{channel_id}/members/{user_id}")
async def remove_channel_member_endpoint(
    channel_id: str,
    user_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, str | bool]:
    # Allow self leaving or admin removing
    if current_user["user_id"] != user_id:
        require_permission(current_user, "workspace.manage")

    channel = await session.get(Channel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    ensure_tenant_boundaries(current_user, workspace_id=channel.workspace_id)

    success = await remove_channel_member(session, channel_id=channel_id, user_id=user_id)
    return {"status": "ok", "removed": success}


@router.get("/{channel_id}/bookmarks", response_model=list[BookmarkRead])
async def get_channel_bookmarks_endpoint(
    channel_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> list[BookmarkRead]:
    require_permission(current_user, "channel.read")
    channel = await session.get(Channel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    ensure_tenant_boundaries(current_user, workspace_id=channel.workspace_id)

    bookmarks = await list_channel_bookmarks(session, channel_id=channel_id)
    return [
        BookmarkRead(
            id=b.id,
            channel_id=b.channel_id,
            workspace_id=b.workspace_id,
            user_id=b.user_id,
            title=b.title,
            url=b.url,
            created_at=b.created_at,
        )
        for b in bookmarks
    ]


@router.post("/{channel_id}/bookmarks", response_model=BookmarkRead, status_code=201)
async def create_channel_bookmark_endpoint(
    channel_id: str,
    payload: BookmarkCreate,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> BookmarkRead:
    require_permission(current_user, "message.create")
    channel = await session.get(Channel, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    ensure_tenant_boundaries(current_user, workspace_id=channel.workspace_id)

    bm = await create_channel_bookmark(
        session,
        channel_id=channel_id,
        workspace_id=channel.workspace_id,
        user_id=current_user["user_id"],
        title=payload.title,
        url=payload.url,
    )
    return BookmarkRead(
        id=bm.id,
        channel_id=bm.channel_id,
        workspace_id=bm.workspace_id,
        user_id=bm.user_id,
        title=bm.title,
        url=bm.url,
        created_at=bm.created_at,
    )


@router.delete("/{channel_id}/bookmarks/{bookmark_id}")
async def delete_channel_bookmark_endpoint(
    channel_id: str,
    bookmark_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, str | bool]:
    require_permission(current_user, "message.create")
    success = await delete_channel_bookmark(session, bookmark_id=bookmark_id)
    return {"status": "ok", "deleted": success}

