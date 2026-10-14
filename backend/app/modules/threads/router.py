from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.authorization import require_permission
from app.core.tenancy.context import ensure_tenant_boundaries
from app.dependencies import get_current_user, get_db
from app.modules.threads.schemas import ThreadCreate, ThreadRead
from app.modules.threads.service import create_thread, get_thread_by_root_message

router = APIRouter(prefix="/threads", tags=["threads"])


@router.get("/{root_message_id}", response_model=ThreadRead)
async def get_thread(
    root_message_id: str,
    workspace_id: str = Query("ws-default", description="Workspace ID"),
    channel_id: str = Query("ch-default", description="Channel ID"),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ThreadRead:
    require_permission(current_user, "message.read")
    ensure_tenant_boundaries(current_user, workspace_id=workspace_id)

    thread = await get_thread_by_root_message(
        session,
        workspace_id=workspace_id,
        channel_id=channel_id,
        root_message_id=root_message_id,
    )
    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    return ThreadRead(
        id=thread.id,
        workspace_id=thread.workspace_id,
        channel_id=thread.channel_id,
        root_message_id=thread.root_message_id,
        author_id=thread.author_id,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
    )


@router.post("", response_model=ThreadRead, status_code=201)
async def create_thread_endpoint(
    payload: ThreadCreate,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ThreadRead:
    require_permission(current_user, "message.create")
    ensure_tenant_boundaries(current_user, workspace_id=payload.workspace_id)

    author_id = current_user["user_id"]
    thread = await create_thread(
        session,
        workspace_id=payload.workspace_id,
        channel_id=payload.channel_id,
        root_message_id=payload.root_message_id,
        author_id=author_id,
    )
    return ThreadRead(
        id=thread.id,
        workspace_id=thread.workspace_id,
        channel_id=thread.channel_id,
        root_message_id=thread.root_message_id,
        author_id=thread.author_id,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
    )
