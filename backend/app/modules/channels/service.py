import secrets
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.channels.models import Channel, ChannelBookmark, ChannelMember


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


async def update_channel(
    session: AsyncSession,
    *,
    channel_id: str,
    name: str | None = None,
    topic: str | None = None,
    is_archived: bool | None = None,
) -> Channel | None:
    channel = await session.get(Channel, channel_id)
    if not channel:
        return None
    if name is not None:
        channel.name = name
    if topic is not None:
        channel.topic = topic
    if is_archived is not None:
        channel.is_archived = is_archived
    await session.commit()
    await session.refresh(channel)
    return channel


async def delete_channel(session: AsyncSession, *, channel_id: str) -> Channel | None:
    channel = await session.get(Channel, channel_id)
    if not channel:
        return None
    await session.delete(channel)
    await session.commit()
    return channel


async def add_channel_member(
    session: AsyncSession,
    *,
    channel_id: str,
    user_id: str,
    role: str = "member",
) -> ChannelMember:
    existing = await session.scalar(
        select(ChannelMember).where(ChannelMember.channel_id == channel_id, ChannelMember.user_id == user_id)
    )
    if existing:
        return existing
    member = ChannelMember(
        id=f"cm-{secrets.token_hex(8)}",
        channel_id=channel_id,
        user_id=user_id,
        role=role,
        joined_at=datetime.now(timezone.utc),
    )
    session.add(member)
    await session.commit()
    await session.refresh(member)
    return member


async def remove_channel_member(session: AsyncSession, *, channel_id: str, user_id: str) -> bool:
    member = await session.scalar(
        select(ChannelMember).where(ChannelMember.channel_id == channel_id, ChannelMember.user_id == user_id)
    )
    if not member:
        return False
    await session.delete(member)
    await session.commit()
    return True


async def list_channel_members(session: AsyncSession, *, channel_id: str) -> list[ChannelMember]:
    result = await session.execute(select(ChannelMember).where(ChannelMember.channel_id == channel_id))
    return list(result.scalars().all())


async def create_channel_bookmark(
    session: AsyncSession,
    *,
    channel_id: str,
    workspace_id: str,
    user_id: str,
    title: str,
    url: str,
) -> ChannelBookmark:
    bookmark = ChannelBookmark(
        id=f"bm-{secrets.token_hex(8)}",
        channel_id=channel_id,
        workspace_id=workspace_id,
        user_id=user_id,
        title=title,
        url=url,
        created_at=datetime.now(timezone.utc),
    )
    session.add(bookmark)
    await session.commit()
    await session.refresh(bookmark)
    return bookmark


async def list_channel_bookmarks(session: AsyncSession, *, channel_id: str) -> list[ChannelBookmark]:
    result = await session.execute(
        select(ChannelBookmark).where(ChannelBookmark.channel_id == channel_id).order_by(ChannelBookmark.created_at.asc())
    )
    return list(result.scalars().all())


async def delete_channel_bookmark(session: AsyncSession, *, bookmark_id: str) -> bool:
    bookmark = await session.get(ChannelBookmark, bookmark_id)
    if not bookmark:
        return False
    await session.delete(bookmark)
    await session.commit()
    return True

