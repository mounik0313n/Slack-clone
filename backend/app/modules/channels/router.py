from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.modules.channels.schemas import ChannelCreate, ChannelRead
from app.modules.channels.service import create_channel, list_channels

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("", response_model=list[ChannelRead])
async def get_channels(session: AsyncSession = Depends(get_db)) -> list[ChannelRead]:
    channels = await list_channels(session)
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
async def create_channel_endpoint(payload: ChannelCreate, session: AsyncSession = Depends(get_db)) -> ChannelRead:
    channel = await create_channel(
        session,
        workspace_id=payload.workspace_id,
        name=payload.name,
        topic=payload.topic,
        is_private=payload.is_private,
    )
    return ChannelRead(
        id=channel.id,
        workspace_id=channel.workspace_id,
        name=channel.name,
        topic=channel.topic,
        is_private=channel.is_private,
        is_archived=channel.is_archived,
        created_at=channel.created_at,
    )
