from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.authorization import require_permission
from app.core.tenancy.context import ensure_tenant_boundaries
from app.dependencies import get_current_user, get_db
from app.modules.channels.models import Channel, ChannelMember
from app.modules.channels.schemas import ChannelCreate, ChannelRead
from app.modules.channels.service import create_channel

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
