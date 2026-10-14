from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.authorization import require_permission
from app.core.tenancy.context import ensure_tenant_boundaries
from app.dependencies import get_current_user, get_db
from app.modules.read_states.schemas import ReadStateCreate, ReadStateRead
from app.modules.read_states.service import get_read_state, mark_channel_read, unread_count_for_channel

router = APIRouter(prefix="/read-states", tags=["read-states"])


@router.get("/{channel_id}", response_model=ReadStateRead)
async def get_read_state_endpoint(
    channel_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ReadStateRead:
    require_permission(current_user, "message.read")
    user_id = current_user["user_id"]
    workspace_id = current_user.get("workspace_id", "ws-default")

    state = await get_read_state(session, workspace_id=workspace_id, channel_id=channel_id, user_id=user_id)
    if state is None:
        return ReadStateRead(
            id=f"rs-{channel_id}-{user_id}",
            workspace_id=workspace_id,
            channel_id=channel_id,
            user_id=user_id,
            last_read_sequence=0,
            last_read_message_id=None,
            updated_at=datetime.now(timezone.utc),
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


@router.post("/mark-read", response_model=ReadStateRead)
async def mark_channel_read_endpoint(
    payload: ReadStateCreate,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ReadStateRead:
    require_permission(current_user, "message.read")
    user_id = current_user["user_id"]
    workspace_id = payload.workspace_id or current_user.get("workspace_id", "ws-default")
    ensure_tenant_boundaries(current_user, workspace_id=workspace_id)

    state = await mark_channel_read(
        session,
        workspace_id=workspace_id,
        channel_id=payload.channel_id,
        user_id=user_id,
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
async def unread_count_endpoint(
    channel_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, int]:
    require_permission(current_user, "message.read")
    user_id = current_user["user_id"]
    workspace_id = current_user.get("workspace_id", "ws-default")

    count = await unread_count_for_channel(
        session,
        workspace_id=workspace_id,
        channel_id=channel_id,
        user_id=user_id,
    )
    return {"unread_count": count}

