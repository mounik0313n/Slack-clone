from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ConversationMemberRead(BaseModel):
    id: str
    conversation_id: str
    user_id: str
    role: str
    joined_at: datetime


class ConversationRead(BaseModel):
    id: str
    workspace_id: str
    type: str
    name: str | None = None
    created_by: str
    channel_id: str | None = None
    created_at: datetime
    member_ids: list[str] = Field(default_factory=list)


class DirectConversationCreate(BaseModel):
    workspace_id: str
    user_id_a: str
    user_id_b: str


class GroupConversationCreate(BaseModel):
    workspace_id: str
    created_by: str
    name: str | None = None
    member_ids: list[str]
