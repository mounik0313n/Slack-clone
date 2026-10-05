from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.mentions.models import Mention

_MENTION_RE = re.compile(r"@([A-Za-z0-9_.-]+)")
_SPECIAL_MENTIONS = {"here": "channel", "channel": "channel", "everyone": "channel"}


def detect_mentions(body: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for raw_name in _MENTION_RE.findall(body):
        normalized = raw_name.lower()
        if normalized in _SPECIAL_MENTIONS:
            mention_type = _SPECIAL_MENTIONS[normalized]
            key = (normalized, mention_type)
        else:
            mention_type = "user"
            key = (normalized, mention_type)
        if key in seen:
            continue
        seen.add(key)
        found.append({"user_id": normalized, "type": mention_type})
    return found


async def save_mentions_for_message(
    session: AsyncSession,
    *,
    organization_id: str,
    workspace_id: str,
    conversation_id: str,
    message_id: str,
    body: str,
    user_lookup: dict[str, str] | None = None,
) -> list[Mention]:
    user_lookup = user_lookup or {}
    mentions: list[Mention] = []
    seen: set[str] = set()

    for mention in detect_mentions(body):
        normalized = mention["user_id"]
        mention_type = mention["type"]
        if mention_type == "user":
            resolved_user_id = user_lookup.get(normalized, normalized)
            if resolved_user_id in seen:
                continue
            seen.add(resolved_user_id)
            mention_obj = Mention(
                id=f"mnt-{message_id}-{resolved_user_id}",
                organization_id=organization_id,
                workspace_id=workspace_id,
                conversation_id=conversation_id,
                message_id=message_id,
                mentioned_user_id=resolved_user_id,
                mention_type="user",
                created_at=datetime.now(timezone.utc),
            )
            session.add(mention_obj)
            mentions.append(mention_obj)
        else:
            resolved_key = normalized
            if resolved_key in seen:
                continue
            seen.add(resolved_key)
            mention_obj = Mention(
                id=f"mnt-{message_id}-{resolved_key}",
                organization_id=organization_id,
                workspace_id=workspace_id,
                conversation_id=conversation_id,
                message_id=message_id,
                mentioned_user_id=resolved_key,
                mention_type="channel",
                created_at=datetime.now(timezone.utc),
            )
            session.add(mention_obj)
            mentions.append(mention_obj)

    await session.commit()
    for mention_obj in mentions:
        await session.refresh(mention_obj)
    return mentions
