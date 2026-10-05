from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class MentionRead(BaseModel):
    id: str
    organization_id: str
    workspace_id: str
    conversation_id: str
    message_id: str
    mentioned_user_id: str
    mention_type: str
    created_at: datetime


class MentionCreate(BaseModel):
    organization_id: str
    workspace_id: str
    conversation_id: str
    message_id: str
    mentioned_user_id: str
    mention_type: str = "user"
