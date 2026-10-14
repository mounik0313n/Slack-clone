from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.authorization import require_permission
from app.core.tenancy.context import ensure_tenant_boundaries
from app.dependencies import get_current_user, get_db
from app.modules.workspaces.models import Workspace
from app.modules.workspaces.schemas import (
    WorkspaceCreate,
    WorkspaceInvite,
    WorkspaceMemberAdd,
    WorkspaceMemberRead,
    WorkspaceRead,
)
from app.modules.workspaces.service import (
    add_workspace_member,
    create_workspace,
    list_workspace_members,
    list_workspaces,
    remove_workspace_member,
)

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
async def create_workspace_endpoint(
    payload: WorkspaceCreate,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> WorkspaceRead:
    creator_id = current_user.get("user_id") if isinstance(current_user, dict) else None
    workspace = await create_workspace(
        session,
        organization_id=payload.organization_id,
        name=payload.name,
        slug=payload.slug,
        creator_user_id=creator_id,
    )
    return WorkspaceRead(
        id=workspace.id,
        organization_id=workspace.organization_id,
        name=workspace.name,
        slug=workspace.slug,
        created_at=workspace.created_at,
    )


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberRead])
async def get_workspace_members_endpoint(
    workspace_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> list[WorkspaceMemberRead]:
    require_permission(current_user, "member.read")
    ensure_tenant_boundaries(current_user, workspace_id=workspace_id)

    members = await list_workspace_members(session, workspace_id=workspace_id)
    return [
        WorkspaceMemberRead(
            id=m.id,
            workspace_id=m.workspace_id,
            user_id=m.user_id,
            role=m.role,
            joined_at=m.joined_at,
        )
        for m in members
    ]


@router.post("/{workspace_id}/members", response_model=WorkspaceMemberRead, status_code=201)
async def add_workspace_member_endpoint(
    workspace_id: str,
    payload: WorkspaceMemberAdd,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> WorkspaceMemberRead:
    require_permission(current_user, "workspace.manage")
    ensure_tenant_boundaries(current_user, workspace_id=workspace_id)

    member = await add_workspace_member(
        session,
        workspace_id=workspace_id,
        user_id=payload.user_id,
        role=payload.role,
    )
    return WorkspaceMemberRead(
        id=member.id,
        workspace_id=member.workspace_id,
        user_id=member.user_id,
        role=member.role,
        joined_at=member.joined_at,
    )


@router.delete("/{workspace_id}/members/{user_id}")
async def remove_workspace_member_endpoint(
    workspace_id: str,
    user_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, str | bool]:
    require_permission(current_user, "workspace.manage")
    ensure_tenant_boundaries(current_user, workspace_id=workspace_id)

    removed = await remove_workspace_member(session, workspace_id=workspace_id, user_id=user_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Workspace member not found")
    return {"status": "ok", "removed": True}

