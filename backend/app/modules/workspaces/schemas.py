from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WorkspaceCreate(BaseModel):
    organization_id: str
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=128)


class WorkspaceRead(BaseModel):
    id: str
    organization_id: str
    name: str
    slug: str
    created_at: datetime
