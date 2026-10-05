from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.modules.sync.service import collect_sync_snapshot

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("", response_model=dict)
async def sync_snapshot(
    user_id: str = Query(..., description="Authenticated user id"),
    workspace_id: str = Query(..., description="Workspace to sync"),
    cursor: str | None = Query(default=None, description="Sequence-based cursor"),
    limit: int = Query(default=200, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
) -> dict:
    return await collect_sync_snapshot(
        session,
        user_id=user_id,
        workspace_id=workspace_id,
        cursor=cursor,
        limit=limit,
    )
