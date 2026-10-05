from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.threads.models import Thread


async def create_thread(
    session: AsyncSession,
    *,
    workspace_id: str,
    channel_id: str,
    root_message_id: str,
    author_id: str,
) -> Thread:
    thread = Thread(
        id="th-" + root_message_id,
        workspace_id=workspace_id,
        channel_id=channel_id,
        root_message_id=root_message_id,
        author_id=author_id,
        created_at=datetime.now(timezone.utc),
    )
    session.add(thread)
    await session.commit()
    await session.refresh(thread)
    return thread


async def get_thread_by_root_message(
    session: AsyncSession,
    *,
    workspace_id: str,
    channel_id: str,
    root_message_id: str,
) -> Thread | None:
    result = await session.execute(
        select(Thread).where(
            Thread.workspace_id == workspace_id,
            Thread.channel_id == channel_id,
            Thread.root_message_id == root_message_id,
        )
    )
    return result.scalars().first()
