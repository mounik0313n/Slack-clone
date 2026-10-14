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


class WorkspaceMemberAdd(BaseModel):
    user_id: str
    role: str = "member"


class WorkspaceMemberRead(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    role: str
    joined_at: datetime


class WorkspaceInvite(BaseModel):
    email: str
    role: str = "member"

