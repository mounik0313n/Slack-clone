from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ReadStateCreate(BaseModel):
    workspace_id: str
    channel_id: str
    user_id: str
    last_read_sequence: int = Field(default=0, ge=0)
    last_read_message_id: str | None = None


class ReadStateRead(BaseModel):
    id: str
    workspace_id: str
    channel_id: str
    user_id: str
    last_read_sequence: int
    last_read_message_id: str | None = None
    updated_at: datetime | None = None
