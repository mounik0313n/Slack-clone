from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenancy.context import ensure_tenant_boundaries
from app.dependencies import get_current_user, get_db
from app.modules.sync.service import collect_sync_snapshot

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("", response_model=dict)
async def sync_snapshot(
    workspace_id: str = Query("ws-default", description="Workspace to sync"),
    cursor: str | None = Query(default=None, description="Sequence-based cursor"),
    limit: int = Query(default=200, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    # 1. Enforce tenant boundaries against authenticated user context
    ensure_tenant_boundaries(current_user, workspace_id=workspace_id)

    # 2. Bind identity strictly to verified server token claims (prevent arbitrary user impersonation)
    effective_user_id = current_user["user_id"]

    return await collect_sync_snapshot(
        session,
        user_id=effective_user_id,
        workspace_id=workspace_id,
        cursor=cursor,
        limit=limit,
    )
