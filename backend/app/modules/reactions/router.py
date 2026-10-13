from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_optional_current_user
from app.modules.reactions.schemas import ReactionCreate, ReactionRead
from app.modules.reactions.service import add_reaction, list_reactions, remove_reaction

router = APIRouter(prefix="/reactions", tags=["reactions"])


@router.get("", response_model=list[ReactionRead])
async def get_reactions(
    workspace_id: str | None = None,
    channel_id: str | None = None,
    message_id: str | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[ReactionRead]:
    reactions = await list_reactions(
        session,
        workspace_id=workspace_id,
        channel_id=channel_id,
        message_id=message_id,
    )
    return [
        ReactionRead(
            id=reaction.id,
            workspace_id=reaction.workspace_id,
            channel_id=reaction.channel_id,
            message_id=reaction.message_id,
            user_id=reaction.user_id,
            emoji=reaction.emoji,
            created_at=reaction.created_at,
        )
        for reaction in reactions
    ]


@router.post("", response_model=ReactionRead, status_code=201)
async def create_reaction(
    payload: ReactionCreate,
    session: AsyncSession = Depends(get_db),
    current_user: dict | None = Depends(get_optional_current_user),
) -> ReactionRead:
    user_id = current_user["user_id"] if isinstance(current_user, dict) else payload.user_id

    reaction = await add_reaction(
        session,
        workspace_id=payload.workspace_id,
        channel_id=payload.channel_id,
        message_id=payload.message_id,
        user_id=user_id,
        emoji=payload.emoji,
    )
    try:
        from app.main import realtime_gateway
        await realtime_gateway.broadcast(
            "reaction.created",
            {
                "reaction_id": reaction.id,
                "workspace_id": reaction.workspace_id,
                "channel_id": reaction.channel_id,
                "message_id": reaction.message_id,
                "user_id": reaction.user_id,
                "emoji": reaction.emoji,
            },
            channel=reaction.channel_id,
        )
    except Exception:
        pass

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
    current_user: dict | None = Depends(get_optional_current_user),
) -> dict[str, bool]:
    if isinstance(current_user, dict) and current_user["user_id"] != user_id and current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete other user's reaction")

    removed = await remove_reaction(
        session,
        workspace_id=workspace_id,
        channel_id=channel_id,
        message_id=message_id,
        user_id=user_id,
        emoji=emoji,
    )
    if removed:
        try:
            from app.main import realtime_gateway
            await realtime_gateway.broadcast(
                "reaction.deleted",
                {
                    "workspace_id": workspace_id,
                    "channel_id": channel_id,
                    "message_id": message_id,
                    "user_id": user_id,
                    "emoji": emoji,
                },
                channel=channel_id,
            )
        except Exception:
            pass

    return {"removed": removed}
