from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.modules.workspaces.schemas import WorkspaceCreate, WorkspaceRead
from app.modules.workspaces.service import create_workspace, list_workspaces

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("", response_model=list[WorkspaceRead])
async def get_workspaces(session: AsyncSession = Depends(get_db)) -> list[WorkspaceRead]:
    workspaces = await list_workspaces(session)
    return [
        WorkspaceRead(
            id=workspace.id,
            organization_id=workspace.organization_id,
            name=workspace.name,
            slug=workspace.slug,
            created_at=workspace.created_at,
        )
        for workspace in workspaces
    ]


@router.post("", response_model=WorkspaceRead, status_code=201)
async def create_workspace_endpoint(payload: WorkspaceCreate, session: AsyncSession = Depends(get_db)) -> WorkspaceRead:
    workspace = await create_workspace(session, organization_id=payload.organization_id, name=payload.name, slug=payload.slug)
    return WorkspaceRead(
        id=workspace.id,
        organization_id=workspace.organization_id,
        name=workspace.name,
        slug=workspace.slug,
        created_at=workspace.created_at,
    )
