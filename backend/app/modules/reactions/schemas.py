from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ReactionCreate(BaseModel):
    workspace_id: str
    channel_id: str
    message_id: str
    user_id: str
    emoji: str


class ReactionRead(BaseModel):
    id: str
    workspace_id: str
    channel_id: str
    message_id: str
    user_id: str
    emoji: str
    created_at: datetime
