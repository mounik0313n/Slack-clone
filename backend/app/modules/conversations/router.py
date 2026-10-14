from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.authorization import require_permission
from app.core.tenancy.context import ensure_tenant_boundaries
from app.dependencies import get_current_user, get_db
from app.modules.conversations.schemas import ConversationRead, DirectConversationCreate, GroupConversationCreate
from app.modules.conversations.service import create_direct_conversation, create_group_conversation, list_conversations_for_user

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationRead])
async def get_conversations(
    workspace_id: str = Query("ws-default", description="Workspace ID"),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> list[ConversationRead]:
    require_permission(current_user, "message.read")
    ensure_tenant_boundaries(current_user, workspace_id=workspace_id)

    # Scoped strictly to the authenticated caller's own conversations
    caller_id = current_user["user_id"]
    conversations = await list_conversations_for_user(session, workspace_id=workspace_id, user_id=caller_id)

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
    current_user: dict = Depends(get_current_user),
) -> ConversationRead:
    require_permission(current_user, "message.create")
    ensure_tenant_boundaries(current_user, workspace_id=payload.workspace_id)

    # Caller must be one of the DM participants
    caller_id = current_user["user_id"]
    if caller_id not in {payload.user_id_a, payload.user_id_b}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated user must be a participant in direct conversation",
        )

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
    current_user: dict = Depends(get_current_user),
) -> ConversationRead:
    require_permission(current_user, "message.create")
    ensure_tenant_boundaries(current_user, workspace_id=payload.workspace_id)

    caller_id = current_user["user_id"]
    if payload.created_by != caller_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Created-by identity must match authenticated user",
        )

    all_members = sorted({caller_id, *payload.member_ids})
    conversation = await create_group_conversation(
        session,
        workspace_id=payload.workspace_id,
        created_by=caller_id,
        name=payload.name,
        member_ids=all_members,
    )
    return ConversationRead(
        id=conversation.id,
        workspace_id=conversation.workspace_id,
        type=conversation.type,
        name=conversation.name,
        created_by=conversation.created_by,
        channel_id=conversation.channel_id,
        created_at=conversation.created_at,
        member_ids=all_members,
    )
