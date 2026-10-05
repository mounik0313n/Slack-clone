from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.modules.organizations.schemas import OrganizationCreate, OrganizationRead
from app.modules.organizations.service import create_organization, list_organizations

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("", response_model=list[OrganizationRead])
async def get_organizations(session: AsyncSession = Depends(get_db)) -> list[OrganizationRead]:
    organizations = await list_organizations(session)
    return [
        OrganizationRead(
            id=organization.id,
            name=organization.name,
            slug=organization.slug,
            created_at=organization.created_at,
        )
        for organization in organizations
    ]


@router.post("", response_model=OrganizationRead, status_code=201)
async def create_organization_endpoint(payload: OrganizationCreate, session: AsyncSession = Depends(get_db)) -> OrganizationRead:
    org = await create_organization(session, name=payload.name, slug=payload.slug)
    return OrganizationRead(id=org.id, name=org.name, slug=org.slug, created_at=org.created_at)
