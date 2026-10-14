import secrets
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.workspaces.models import Workspace, WorkspaceMember


async def create_workspace(
    session: AsyncSession,
    *,
    organization_id: str,
    name: str,
    slug: str,
    creator_user_id: str | None = None,
) -> Workspace:
    workspace = Workspace(id="ws-" + slug.lower().replace(" ", "-"), organization_id=organization_id, name=name, slug=slug.lower())
    session.add(workspace)
    await session.flush()

    if creator_user_id:
        member = WorkspaceMember(
            id=f"wm-{secrets.token_hex(8)}",
            workspace_id=workspace.id,
            user_id=creator_user_id,
            role="admin",
            joined_at=datetime.now(timezone.utc),
        )
        session.add(member)

    await session.commit()
    await session.refresh(workspace)
    return workspace


async def list_workspaces(session: AsyncSession, organization_id: str | None = None) -> list[Workspace]:
    query = select(Workspace)
    if organization_id:
        query = query.where(Workspace.organization_id == organization_id)
    query = query.order_by(Workspace.created_at.desc())
    result = await session.execute(query)
    return list(result.scalars().all())


async def add_workspace_member(
    session: AsyncSession,
    *,
    workspace_id: str,
    user_id: str,
    role: str = "member",
) -> WorkspaceMember:
    existing = await session.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    if existing:
        return existing
    member = WorkspaceMember(
        id=f"wm-{secrets.token_hex(8)}",
        workspace_id=workspace_id,
        user_id=user_id,
        role=role,
        joined_at=datetime.now(timezone.utc),
    )
    session.add(member)
    await session.commit()
    await session.refresh(member)
    return member


async def list_workspace_members(session: AsyncSession, *, workspace_id: str) -> list[WorkspaceMember]:
    result = await session.execute(
        select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id).order_by(WorkspaceMember.joined_at.asc())
    )
    return list(result.scalars().all())


async def remove_workspace_member(session: AsyncSession, *, workspace_id: str, user_id: str) -> bool:
    member = await session.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    if not member:
        return False
    await session.delete(member)
    await session.commit()
    return True

