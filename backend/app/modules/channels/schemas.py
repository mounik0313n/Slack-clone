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


class ChannelUpdate(BaseModel):
    name: str | None = None
    topic: str | None = None
    is_archived: bool | None = None


class ChannelMemberAdd(BaseModel):
    user_id: str
    role: str = "member"


class ChannelMemberRead(BaseModel):
    id: str
    channel_id: str
    user_id: str
    role: str
    joined_at: datetime


class BookmarkCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=1, max_length=512)


class BookmarkRead(BaseModel):
    id: str
    channel_id: str
    workspace_id: str
    user_id: str
    title: str
    url: str
    created_at: datetime
