from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.organizations.models import Organization


async def create_organization(session: AsyncSession, *, name: str, slug: str) -> Organization:
    org = Organization(id="org-" + slug.lower().replace(" ", "-"), name=name, slug=slug.lower())
    session.add(org)
    await session.commit()
    await session.refresh(org)
    return org


async def list_organizations(session: AsyncSession) -> list[Organization]:
    result = await session.execute(select(Organization).order_by(Organization.created_at.desc()))
    return list(result.scalars().all())
