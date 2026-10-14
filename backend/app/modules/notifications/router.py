from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.authorization import require_permission
from app.dependencies import get_current_user, get_db
from app.modules.notifications.service import create_notification, list_notifications_for_user, mark_notification_read

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationCreateInput(BaseModel):
    organization_id: str
    workspace_id: str
    recipient_user_id: str
    actor_user_id: str | None = None
    type: str = "MENTION"
    conversation_id: str | None = None
    message_id: str | None = None
    thread_id: str | None = None
    payload: dict | None = None


@router.get("", response_model=list[dict])
async def get_notifications(
    user_id: str | None = None,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    require_permission(current_user, "message.read")
    target_user_id = current_user["user_id"] if user_id is None else user_id
    notifications = await list_notifications_for_user(session, user_id=target_user_id)
    return [
        {
            "id": notification.id,
            "recipient_user_id": notification.recipient_user_id,
            "actor_user_id": notification.actor_user_id,
            "type": notification.type,
            "conversation_id": notification.conversation_id,
            "message_id": notification.message_id,
            "thread_id": notification.thread_id,
            "payload": notification.payload,
            "read_at": notification.read_at.isoformat() if notification.read_at else None,
            "created_at": notification.created_at.isoformat(),
        }
        for notification in notifications
    ]


@router.post("", response_model=dict, status_code=201)
async def create_notification_endpoint(
    payload: NotificationCreateInput,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    require_permission(current_user, "message.create")
    notification = await create_notification(
        session,
        organization_id=payload.organization_id,
        workspace_id=payload.workspace_id,
        recipient_user_id=payload.recipient_user_id,
        actor_user_id=current_user.get("user_id", payload.actor_user_id),
        type=payload.type,
        conversation_id=payload.conversation_id,
        message_id=payload.message_id,
        thread_id=payload.thread_id,
        payload=payload.payload,
    )
    return {
        "id": notification.id,
        "recipient_user_id": notification.recipient_user_id,
        "type": notification.type,
        "read_at": notification.read_at.isoformat() if notification.read_at else None,
    }


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: str,
    user_id: str | None = None,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, bool]:
    target_user_id = current_user["user_id"] if user_id is None else user_id
    return {"read": await mark_notification_read(session, notification_id=notification_id, user_id=target_user_id)}

