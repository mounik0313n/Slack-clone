from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.modules.mentions.schemas import MentionCreate, MentionRead
from app.modules.mentions.service import detect_mentions, save_mentions_for_message

router = APIRouter(prefix="/mentions", tags=["mentions"])


@router.post("/detect")
async def detect_mentions_route(body: dict[str, str]) -> list[dict[str, str]]:
    return detect_mentions(body.get("text", ""))


@router.post("", response_model=list[MentionRead], status_code=201)
async def create_mentions_endpoint(payload: MentionCreate, session: AsyncSession = Depends(get_db)) -> list[MentionRead]:
    mentions = await save_mentions_for_message(
        session,
        organization_id=payload.organization_id,
        workspace_id=payload.workspace_id,
        conversation_id=payload.conversation_id,
        message_id=payload.message_id,
        body="@" + payload.mentioned_user_id,
        user_lookup={payload.mentioned_user_id: payload.mentioned_user_id},
    )
    return [
        MentionRead(
            id=mention.id,
            organization_id=mention.organization_id,
            workspace_id=mention.workspace_id,
            conversation_id=mention.conversation_id,
            message_id=mention.message_id,
            mentioned_user_id=mention.mentioned_user_id,
            mention_type=mention.mention_type,
            created_at=mention.created_at,
        )
        for mention in mentions
    ]
