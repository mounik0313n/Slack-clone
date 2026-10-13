from __future__ import annotations

from pydantic import BaseModel


class SummarizeRequest(BaseModel):
    channel_id: str
    limit: int = 20


class SummarizeResponse(BaseModel):
    channel_id: str
    message_count: int
    summary: str


class QueryRequest(BaseModel):
    query: str
    channel_id: str | None = None


class QueryResponse(BaseModel):
    answer: str
    model: str = "neon-ai-gateway"
