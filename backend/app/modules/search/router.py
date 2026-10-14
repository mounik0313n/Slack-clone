from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.authorization import require_permission
from app.core.tenancy.context import ensure_tenant_boundaries
from app.dependencies import get_current_user, get_db
from app.modules.channels.models import Channel, ChannelMember
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
    current_user: dict = Depends(get_current_user),
) -> SearchResponse:
    # 1. Require verified authentication & message read permission
    require_permission(current_user, "message.read")

    # 2. Enforce strict tenant boundary
    ensure_tenant_boundaries(current_user, workspace_id=workspace_id)

    # 3. Channel access verification & private data exposure prevention
    if channel_id:
        channel = await session.get(Channel, channel_id)
        if not channel or channel.workspace_id != workspace_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found in this workspace")

        if channel.is_private:
            is_member = await session.scalar(
                select(ChannelMember).where(
                    ChannelMember.channel_id == channel_id,
                    ChannelMember.user_id == current_user["user_id"],
                )
            )
            if not is_member and current_user.get("role") != "admin":
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to private channel")

        db_query = select(Message).where(
            Message.workspace_id == workspace_id,
            Message.channel_id == channel_id,
            Message.body.ilike(f"%{query}%"),
        )
    else:
        # Global search: only search public channels or private channels user belongs to
        public_channels_subquery = select(Channel.id).where(
            Channel.workspace_id == workspace_id,
            Channel.is_private == False,  # noqa: E712
        )
        user_private_channels_subquery = (
            select(ChannelMember.channel_id)
            .join(Channel, Channel.id == ChannelMember.channel_id)
            .where(
                Channel.workspace_id == workspace_id,
                ChannelMember.user_id == current_user["user_id"],
            )
        )

        if current_user.get("role") == "admin":
            db_query = select(Message).where(
                Message.workspace_id == workspace_id,
                Message.body.ilike(f"%{query}%"),
            )
        else:
            db_query = select(Message).where(
                Message.workspace_id == workspace_id,
                Message.body.ilike(f"%{query}%"),
                or_(
                    Message.channel_id.in_(public_channels_subquery),
                    Message.channel_id.in_(user_private_channels_subquery),
                ),
            )

    db_query = db_query.order_by(Message.sequence.desc()).limit(limit)
    result = await session.execute(db_query)
    messages = list(result.scalars().all())

    results = []
    for m in messages:
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
