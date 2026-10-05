from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.modules.threads.schemas import ThreadCreate, ThreadRead
from app.modules.threads.service import create_thread, get_thread_by_root_message

router = APIRouter(prefix="/threads", tags=["threads"])


@router.get("/{root_message_id}", response_model=ThreadRead)
async def get_thread(
    root_message_id: str,
    workspace_id: str = "ws-default",
    channel_id: str = "ch-default",
    session: AsyncSession = Depends(get_db),
) -> ThreadRead:
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
async def create_thread_endpoint(payload: ThreadCreate, session: AsyncSession = Depends(get_db)) -> ThreadRead:
    thread = await create_thread(
        session,
        workspace_id=payload.workspace_id,
        channel_id=payload.channel_id,
        root_message_id=payload.root_message_id,
        author_id=payload.author_id,
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
