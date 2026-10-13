from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class SearchResultItem(BaseModel):
    id: str
    workspace_id: str
    channel_id: str
    author_id: str
    body: str
    created_at: datetime
    snippet: str


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchResultItem]
