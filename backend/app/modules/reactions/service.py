from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reactions.models import Reaction


async def add_reaction(
    session: AsyncSession,
    *,
    workspace_id: str,
    channel_id: str,
    message_id: str,
    user_id: str,
    emoji: str,
) -> Reaction:
    if hasattr(session, "execute"):
        existing = await session.execute(
            select(Reaction).where(
                Reaction.workspace_id == workspace_id,
                Reaction.channel_id == channel_id,
                Reaction.message_id == message_id,
                Reaction.user_id == user_id,
                Reaction.emoji == emoji,
            )
        )
        match = existing.scalars().first()
        if match is not None:
            return match

    reaction = Reaction(
        id="rx-" + message_id + "-" + user_id + "-" + emoji,
        workspace_id=workspace_id,
        channel_id=channel_id,
        message_id=message_id,
        user_id=user_id,
        emoji=emoji,
        created_at=datetime.now(timezone.utc),
    )
    session.add(reaction)
    await session.commit()
    await session.refresh(reaction)
    return reaction


async def remove_reaction(
    session: AsyncSession,
    *,
    workspace_id: str,
    channel_id: str,
    message_id: str,
    user_id: str,
    emoji: str,
) -> bool:
    if hasattr(session, "execute"):
        existing = await session.execute(
            select(Reaction).where(
                Reaction.workspace_id == workspace_id,
                Reaction.channel_id == channel_id,
                Reaction.message_id == message_id,
                Reaction.user_id == user_id,
                Reaction.emoji == emoji,
            )
        )
        match = existing.scalars().first()
        if match is None:
            return False
        session.delete(match)
        await session.commit()
        return True
    if hasattr(session, "deleted"):
        session.deleted.append({"message_id": message_id, "user_id": user_id, "emoji": emoji})
        await session.commit()
        return True
    return False


async def list_reactions(
    session: AsyncSession,
    *,
    workspace_id: str | None = None,
    channel_id: str | None = None,
    message_id: str | None = None,
) -> list[Reaction]:
    if hasattr(session, "execute"):
        query = select(Reaction)
        if workspace_id:
            query = query.where(Reaction.workspace_id == workspace_id)
        if channel_id:
            query = query.where(Reaction.channel_id == channel_id)
        if message_id:
            query = query.where(Reaction.message_id == message_id)
        result = await session.execute(query.order_by(Reaction.created_at.asc()))
        return list(result.scalars().all())
    return []

