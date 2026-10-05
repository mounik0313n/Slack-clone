from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.modules.conversations.schemas import ConversationRead, DirectConversationCreate, GroupConversationCreate
from app.modules.conversations.service import create_direct_conversation, create_group_conversation, list_conversations_for_user

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationRead])
async def get_conversations(
    workspace_id: str,
    user_id: str,
    session: AsyncSession = Depends(get_db),
) -> list[ConversationRead]:
    conversations = await list_conversations_for_user(session, workspace_id=workspace_id, user_id=user_id)
    return [
        ConversationRead(
            id=conversation.id,
            workspace_id=conversation.workspace_id,
            type=conversation.type,
            name=conversation.name,
            created_by=conversation.created_by,
            channel_id=conversation.channel_id,
            created_at=conversation.created_at,
            member_ids=[],
        )
        for conversation in conversations
    ]


@router.post("/direct", response_model=ConversationRead, status_code=201)
async def create_direct_conversation_endpoint(
    payload: DirectConversationCreate,
    session: AsyncSession = Depends(get_db),
) -> ConversationRead:
    conversation = await create_direct_conversation(
        session,
        workspace_id=payload.workspace_id,
        user_id_a=payload.user_id_a,
        user_id_b=payload.user_id_b,
    )
    return ConversationRead(
        id=conversation.id,
        workspace_id=conversation.workspace_id,
        type=conversation.type,
        name=conversation.name,
        created_by=conversation.created_by,
        channel_id=conversation.channel_id,
        created_at=conversation.created_at,
        member_ids=[payload.user_id_a, payload.user_id_b],
    )


@router.post("/group", response_model=ConversationRead, status_code=201)
async def create_group_conversation_endpoint(
    payload: GroupConversationCreate,
    session: AsyncSession = Depends(get_db),
) -> ConversationRead:
    conversation = await create_group_conversation(
        session,
        workspace_id=payload.workspace_id,
        created_by=payload.created_by,
        name=payload.name,
        member_ids=payload.member_ids,
    )
    return ConversationRead(
        id=conversation.id,
        workspace_id=conversation.workspace_id,
        type=conversation.type,
        name=conversation.name,
        created_by=conversation.created_by,
        channel_id=conversation.channel_id,
        created_at=conversation.created_at,
        member_ids=sorted({payload.created_by, *payload.member_ids}),
    )
