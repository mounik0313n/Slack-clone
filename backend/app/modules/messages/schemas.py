from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    workspace_id: str
    channel_id: str
    author_id: str
    body: str = Field(min_length=1, max_length=20000)
    thread_id: str | None = None
    client_message_id: str | None = None


class MessageRead(BaseModel):
    id: str
    workspace_id: str
    channel_id: str
    author_id: str
    sequence: int
    body: str
    thread_id: str | None
    client_message_id: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
