from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.workspaces.models import Workspace


async def create_workspace(session: AsyncSession, *, organization_id: str, name: str, slug: str) -> Workspace:
    workspace = Workspace(id="ws-" + slug.lower().replace(" ", "-"), organization_id=organization_id, name=name, slug=slug.lower())
    session.add(workspace)
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
