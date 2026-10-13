from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_optional_current_user
from app.modules.messages.models import Message
from app.modules.search.schemas import SearchResponse, SearchResultItem

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/messages", response_model=SearchResponse)
async def search_messages_endpoint(
    query: str = Query(..., min_length=1, description="Search keyword"),
    channel_id: str | None = None,
    workspace_id: str = "ws-default",
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    current_user: dict | None = Depends(get_optional_current_user),
) -> SearchResponse:
    db_query = select(Message).where(
        Message.workspace_id == workspace_id,
        Message.body.ilike(f"%{query}%"),
    )
    if channel_id:
        db_query = db_query.where(Message.channel_id == channel_id)

    db_query = db_query.order_by(Message.sequence.desc()).limit(limit)
    result = await session.execute(db_query)
    messages = list(result.scalars().all())

    results = []
    for m in messages:
        # Create context snippet with match preview
        body = m.body
        snippet = body if len(body) <= 120 else body[:117] + "..."
        results.append(
            SearchResultItem(
                id=m.id,
                workspace_id=m.workspace_id,
                channel_id=m.channel_id,
                author_id=m.author_id,
                body=m.body,
                created_at=m.created_at,
                snippet=snippet,
            )
        )

    return SearchResponse(query=query, total=len(results), results=results)
