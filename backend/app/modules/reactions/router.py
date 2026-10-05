from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.modules.reactions.schemas import ReactionCreate, ReactionRead
from app.modules.reactions.service import add_reaction, remove_reaction

router = APIRouter(prefix="/reactions", tags=["reactions"])


@router.post("", response_model=ReactionRead, status_code=201)
async def create_reaction(payload: ReactionCreate, session: AsyncSession = Depends(get_db)) -> ReactionRead:
    reaction = await add_reaction(
        session,
        workspace_id=payload.workspace_id,
        channel_id=payload.channel_id,
        message_id=payload.message_id,
        user_id=payload.user_id,
        emoji=payload.emoji,
    )
    return ReactionRead(
        id=reaction.id,
        workspace_id=reaction.workspace_id,
        channel_id=reaction.channel_id,
        message_id=reaction.message_id,
        user_id=reaction.user_id,
        emoji=reaction.emoji,
        created_at=reaction.created_at,
    )


@router.delete("/{message_id}/{user_id}/{emoji}")
async def delete_reaction(
    message_id: str,
    user_id: str,
    emoji: str,
    workspace_id: str = "ws-default",
    channel_id: str = "ch-default",
    session: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    removed = await remove_reaction(
        session,
        workspace_id=workspace_id,
        channel_id=channel_id,
        message_id=message_id,
        user_id=user_id,
        emoji=emoji,
    )
    return {"removed": removed}
