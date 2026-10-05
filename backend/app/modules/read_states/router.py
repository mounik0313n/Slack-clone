from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.modules.read_states.schemas import ReadStateCreate, ReadStateRead
from app.modules.read_states.service import get_read_state, mark_channel_read, unread_count_for_channel

router = APIRouter(prefix="/read-states", tags=["read-states"])


@router.get("/{channel_id}", response_model=ReadStateRead)
async def get_read_state_endpoint(channel_id: str, session: AsyncSession = Depends(get_db), user_id: str = "user-1") -> ReadStateRead:
    state = await get_read_state(session, workspace_id="ws-default", channel_id=channel_id, user_id=user_id)
    if state is None:
        raise ValueError("No read state found")
    return ReadStateRead(
        id=state.id,
        workspace_id=state.workspace_id,
        channel_id=state.channel_id,
        user_id=state.user_id,
        last_read_sequence=state.last_read_sequence,
        last_read_message_id=state.last_read_message_id,
        updated_at=state.updated_at,
    )


@router.post("/mark-read", response_model=ReadStateRead)
async def mark_channel_read_endpoint(payload: ReadStateCreate, session: AsyncSession = Depends(get_db)) -> ReadStateRead:
    state = await mark_channel_read(
        session,
        workspace_id=payload.workspace_id,
        channel_id=payload.channel_id,
        user_id=payload.user_id,
        last_read_sequence=payload.last_read_sequence,
        last_read_message_id=payload.last_read_message_id,
    )
    return ReadStateRead(
        id=state.id,
        workspace_id=state.workspace_id,
        channel_id=state.channel_id,
        user_id=state.user_id,
        last_read_sequence=state.last_read_sequence,
        last_read_message_id=state.last_read_message_id,
        updated_at=state.updated_at,
    )


@router.get("/{channel_id}/unread-count")
async def unread_count_endpoint(channel_id: str, session: AsyncSession = Depends(get_db), user_id: str = "user-1") -> dict[str, int]:
    count = await unread_count_for_channel(
        session,
        workspace_id="ws-default",
        channel_id=channel_id,
        user_id=user_id,
    )
    return {"unread_count": count}
