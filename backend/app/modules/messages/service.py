from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox.service import emit_outbox_event
from app.modules.mentions.service import save_mentions_for_message
from app.modules.messages.models import Message
from app.modules.notifications.service import create_notification


def next_sequence_for_channel(existing_sequences: list[int]) -> int:
    if not existing_sequences:
        return 1
    return max(existing_sequences) + 1


async def create_message(
    session: AsyncSession,
    *,
    workspace_id: str,
    channel_id: str,
    author_id: str,
    body: str,
    thread_id: str | None,
    client_message_id: str | None = None,
) -> Message:
    if client_message_id:
        existing = await session.execute(
            select(Message).where(
                Message.workspace_id == workspace_id,
                Message.channel_id == channel_id,
                Message.client_message_id == client_message_id,
            )
        )
        duplicate = existing.scalars().first()
        if duplicate is not None:
            return duplicate

    result = await session.execute(select(Message.sequence).where(Message.channel_id == channel_id, Message.workspace_id == workspace_id))
    existing_sequences = list(result.scalars().all())
    sequence = next_sequence_for_channel(existing_sequences)

    message = Message(
        id="msg-" + str(abs(hash(body + author_id + channel_id + str(sequence))))[:12],
        workspace_id=workspace_id,
        channel_id=channel_id,
        author_id=author_id,
        sequence=sequence,
        body=body,
        thread_id=thread_id,
        client_message_id=client_message_id,
        created_at=datetime.now(timezone.utc),
    )
    session.add(message)
    await emit_outbox_event(
        session,
        event_type="message.created",
        aggregate_type="message",
        aggregate_id=message.id,
        payload={
            "message_id": message.id,
            "workspace_id": workspace_id,
            "channel_id": channel_id,
            "author_id": author_id,
            "body": body,
            "thread_id": thread_id,
            "sequence": sequence,
            "client_message_id": client_message_id,
        },
        organization_id="org-default",
        workspace_id=workspace_id,
        conversation_id=channel_id,
        actor_user_id=author_id,
        sequence=sequence,
    )
    try:
        mentions = await save_mentions_for_message(
            session,
            organization_id="org-default",
            workspace_id=workspace_id,
            conversation_id=channel_id,
            message_id=message.id,
            body=body,
            user_lookup={},
        )
        for mention in mentions:
            if mention.mention_type == "user":
                await create_notification(
                    session,
                    organization_id="org-default",
                    workspace_id=workspace_id,
                    recipient_user_id=mention.mentioned_user_id,
                    actor_user_id=author_id,
                    type="MENTION",
                    conversation_id=channel_id,
                    message_id=message.id,
                    payload={"body": body},
                )
    except Exception:
        pass
    await session.commit()
    await session.refresh(message)
    return message


async def list_messages(
    session: AsyncSession,
    channel_id: str | None = None,
    thread_id: str | None = None,
    limit: int = 100,
    before_sequence: int | None = None,
) -> list[Message]:
    query = select(Message)
    if channel_id:
        query = query.where(Message.channel_id == channel_id)
    if thread_id is not None:
        query = query.where(Message.thread_id == thread_id)
    if before_sequence is not None:
        query = query.where(Message.sequence < before_sequence)
    result = await session.execute(query.order_by(Message.sequence.asc()).limit(limit))
    return list(result.scalars().all())


async def update_message(
    session: AsyncSession,
    *,
    message_id: str,
    body: str,
    actor_id: str,
    is_admin: bool = False,
) -> Message | None:
    message = await session.get(Message, message_id)
    if not message:
        return None
    if message.author_id != actor_id and not is_admin:
        raise PermissionError("Cannot edit another user's message")
    message.body = body
    message.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(message)
    return message


async def delete_message(
    session: AsyncSession,
    *,
    message_id: str,
    actor_id: str,
    is_admin: bool = False,
) -> Message | None:
    message = await session.get(Message, message_id)
    if not message:
        return None
    if message.author_id != actor_id and not is_admin:
        raise PermissionError("Cannot delete another user's message")
    await session.delete(message)
    await session.commit()
    return message


async def toggle_pin_message(
    session: AsyncSession,
    *,
    message_id: str,
    pin: bool | None = None,
) -> Message | None:
    message = await session.get(Message, message_id)
    if not message:
        return None
    message.is_pinned = not message.is_pinned if pin is None else pin
    await session.commit()
    await session.refresh(message)
    return message


async def list_pinned_messages(
    session: AsyncSession,
    channel_id: str,
) -> list[Message]:
    result = await session.execute(
        select(Message).where(Message.channel_id == channel_id, Message.is_pinned == True).order_by(Message.sequence.asc())  # noqa: E712
    )
    return list(result.scalars().all())

