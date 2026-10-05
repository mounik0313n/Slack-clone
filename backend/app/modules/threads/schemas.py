from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ThreadCreate(BaseModel):
    workspace_id: str
    channel_id: str
    root_message_id: str
    author_id: str


class ThreadRead(BaseModel):
    id: str
    workspace_id: str
    channel_id: str
    root_message_id: str
    author_id: str
    created_at: datetime
    updated_at: datetime | None = None
