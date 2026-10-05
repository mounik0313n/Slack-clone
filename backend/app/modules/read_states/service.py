from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.messages.models import Message
from app.modules.read_states.models import ReadState


async def get_read_state(session: AsyncSession, *, workspace_id: str, channel_id: str, user_id: str) -> ReadState | None:
    if not hasattr(session, "execute"):
        return None
    result = await session.execute(
        select(ReadState).where(
            ReadState.workspace_id == workspace_id,
            ReadState.channel_id == channel_id,
            ReadState.user_id == user_id,
        )
    )
    scalars = result.scalars()
    if hasattr(scalars, "first"):
        return scalars.first()
    values = list(scalars.all()) if hasattr(scalars, "all") else []
    return values[0] if values else None


async def mark_channel_read(
    session: AsyncSession,
    *,
    workspace_id: str,
    channel_id: str,
    user_id: str,
    last_read_sequence: int,
    last_read_message_id: str | None,
) -> ReadState:
    state = await get_read_state(session, workspace_id=workspace_id, channel_id=channel_id, user_id=user_id)
    if state is None:
        state = ReadState(
            id="rs-" + user_id + "-" + channel_id,
            workspace_id=workspace_id,
            channel_id=channel_id,
            user_id=user_id,
            last_read_sequence=last_read_sequence,
            last_read_message_id=last_read_message_id,
            updated_at=datetime.now(timezone.utc),
        )
        session.add(state)
    else:
        state.last_read_sequence = max(state.last_read_sequence, last_read_sequence)
        state.last_read_message_id = last_read_message_id or state.last_read_message_id
        state.updated_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(state)
    return state


async def unread_count_for_channel(
    session: AsyncSession,
    *,
    workspace_id: str,
    channel_id: str,
    user_id: str,
    last_read_sequence: int | None = None,
) -> int:
    read_state = await get_read_state(session, workspace_id=workspace_id, channel_id=channel_id, user_id=user_id)
    reference_sequence = last_read_sequence if last_read_sequence is not None else (read_state.last_read_sequence if read_state else 0)

    if not hasattr(session, "execute"):
        return 0
    result = await session.execute(
        select(Message.sequence).where(
            Message.workspace_id == workspace_id,
            Message.channel_id == channel_id,
            Message.sequence > reference_sequence,
        )
    )
    scalars = result.scalars()
    if hasattr(scalars, "all"):
        return len(scalars.all())
    return len(list(scalars))
