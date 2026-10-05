from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ChannelCreate(BaseModel):
    workspace_id: str
    name: str = Field(min_length=2, max_length=128)
    topic: str | None = None
    is_private: bool = False


class ChannelRead(BaseModel):
    id: str
    workspace_id: str
    name: str
    topic: str | None
    is_private: bool
    is_archived: bool
    created_at: datetime
