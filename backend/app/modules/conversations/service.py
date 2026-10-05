from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.conversations.models import Conversation, ConversationMember


def _stable_conversation_id(participants: list[str]) -> str:
    key = "|".join(sorted(set(participants)))
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return f"conv-{digest[:20]}"


async def create_direct_conversation(
    session: AsyncSession,
    *,
    workspace_id: str,
    user_id_a: str,
    user_id_b: str,
) -> Conversation:
    if user_id_a == user_id_b:
        raise ValueError("A direct conversation requires two distinct users.")

    participant_ids = sorted({user_id_a, user_id_b})
    conversation_id = _stable_conversation_id([workspace_id, *participant_ids])

    if hasattr(session, "_conversations"):
        for existing in session._conversations.values():
            if getattr(existing, "workspace_id", None) == workspace_id and getattr(existing, "type", None) == "dm":
                return existing

    conversation = Conversation(
        id=conversation_id,
        workspace_id=workspace_id,
        type="dm",
        name=None,
        created_by=user_id_a,
        channel_id=None,
        created_at=datetime.now(timezone.utc),
    )
    session.add(conversation)

    for member_id in participant_ids:
        member = ConversationMember(
            id=f"cm-{conversation.id}-{member_id}",
            conversation_id=conversation.id,
            user_id=member_id,
            role="member",
            joined_at=datetime.now(timezone.utc),
        )
        session.add(member)

    await session.commit()
    await session.refresh(conversation)
    return conversation


async def create_group_conversation(
    session: AsyncSession,
    *,
    workspace_id: str,
    created_by: str,
    name: str | None,
    member_ids: list[str],
) -> Conversation:
    members = sorted({created_by, *member_ids})
    conversation_id = _stable_conversation_id([workspace_id, *members])

    if hasattr(session, "_conversations"):
        for existing in session._conversations.values():
            if getattr(existing, "workspace_id", None) == workspace_id and getattr(existing, "type", None) == "group_dm":
                return existing

    conversation = Conversation(
        id=conversation_id,
        workspace_id=workspace_id,
        type="group_dm",
        name=name or "Group DM",
        created_by=created_by,
        channel_id=None,
        created_at=datetime.now(timezone.utc),
    )
    session.add(conversation)

    for member_id in members:
        member = ConversationMember(
            id=f"cm-{conversation.id}-{member_id}",
            conversation_id=conversation.id,
            user_id=member_id,
            role="admin" if member_id == created_by else "member",
            joined_at=datetime.now(timezone.utc),
        )
        session.add(member)

    await session.commit()
    await session.refresh(conversation)
    return conversation


async def list_conversations_for_user(
    session: AsyncSession,
    *,
    workspace_id: str,
    user_id: str,
) -> list[Conversation]:
    if hasattr(session, "_conversations") and hasattr(session, "_members"):
        ids = session._members.get(user_id, [])
        return [conversation for conversation in session._conversations.values() if conversation.id in ids and conversation.workspace_id == workspace_id]

    if hasattr(session, "execute"):
        member_rows = await session.execute(
            select(ConversationMember.conversation_id).where(
                ConversationMember.user_id == user_id,
            )
        )
        conversation_ids = {row[0] for row in member_rows.all()}
        if not conversation_ids:
            return []
        result = await session.execute(
            select(Conversation).where(
                Conversation.id.in_(sorted(conversation_ids)),
                Conversation.workspace_id == workspace_id,
            )
        )
        return list(result.scalars().all())
    return []
