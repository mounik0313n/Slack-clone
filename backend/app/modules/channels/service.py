from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.channels.models import Channel


async def create_channel(session: AsyncSession, *, workspace_id: str, name: str, topic: str | None, is_private: bool) -> Channel:
    channel = Channel(
        id="ch-" + name.lower().replace(" ", "-"),
        workspace_id=workspace_id,
        name=name,
        topic=topic,
        is_private=is_private,
        is_archived=False,
    )
    session.add(channel)
    await session.commit()
    await session.refresh(channel)
    return channel


async def list_channels(session: AsyncSession, workspace_id: str | None = None) -> list[Channel]:
    query = select(Channel)
    if workspace_id:
        query = query.where(Channel.workspace_id == workspace_id)
    result = await session.execute(query.order_by(Channel.created_at.desc()))
    return list(result.scalars().all())
