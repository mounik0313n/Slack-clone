from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.authorization import require_permission
from app.dependencies import get_current_user, get_db, get_optional_current_user
from app.modules.admin.schemas import AdminStats, AuditLogItem, MemberRoleUpdate
from app.modules.auth.models import User
from app.modules.channels.models import Channel
from app.modules.files.models import FileAttachment
from app.modules.messages.models import Message

router = APIRouter(prefix="/admin", tags=["admin"])

# In-memory audit log record store for demonstration & testing
_audit_logs: list[dict] = [
    {
        "id": "audit-1",
        "action": "workspace.created",
        "actor_id": "user-1",
        "target_id": "ws-default",
        "timestamp": datetime.now(timezone.utc),
        "details": {"workspace_name": "Acme Inc"},
    },
    {
        "id": "audit-2",
        "action": "channel.created",
        "actor_id": "user-1",
        "target_id": "ch-general",
        "timestamp": datetime.now(timezone.utc),
        "details": {"channel_name": "general"},
    },
]


@router.get("/audit-logs", response_model=list[AuditLogItem])
async def get_audit_logs(
    current_user: dict | None = Depends(get_optional_current_user),
) -> list[AuditLogItem]:
    if isinstance(current_user, dict):
        require_permission(current_user, "audit.read")
    return [
        AuditLogItem(
            id=entry["id"],
            action=entry["action"],
            actor_id=entry["actor_id"],
            target_id=entry.get("target_id"),
            timestamp=entry["timestamp"],
            details=entry.get("details", {}),
        )
        for entry in _audit_logs
    ]


@router.get("/members")
async def get_members(
    session: AsyncSession = Depends(get_db),
    current_user: dict | None = Depends(get_optional_current_user),
) -> list[dict]:
    result = await session.execute(select(User).order_by(User.display_name))
    users = list(result.scalars().all())
    return [
        {
            "id": u.id,
            "email": u.email,
            "username": u.username,
            "display_name": u.display_name,
            "role": "admin" if u.id == "user-1" else "member",
            "is_active": u.is_active,
        }
        for u in users
    ]


@router.patch("/members/{user_id}/role")
async def update_member_role(
    user_id: str,
    payload: MemberRoleUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: dict | None = Depends(get_optional_current_user),
) -> dict[str, str]:
    if isinstance(current_user, dict):
        require_permission(current_user, "workspace.manage")

    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    _audit_logs.append({
        "id": f"audit-{secrets.token_hex(4)}",
        "action": "member.role_updated",
        "actor_id": current_user["user_id"] if isinstance(current_user, dict) else "admin",
        "target_id": user_id,
        "timestamp": datetime.now(timezone.utc),
        "details": {"new_role": payload.role},
    })
    return {"status": "ok", "user_id": user_id, "role": payload.role}


@router.get("/stats", response_model=AdminStats)
async def get_admin_stats(session: AsyncSession = Depends(get_db)) -> AdminStats:
    user_count = await session.scalar(select(func.count(User.id))) or 0
    channel_count = await session.scalar(select(func.count(Channel.id))) or 0
    message_count = await session.scalar(select(func.count(Message.id))) or 0
    file_count = await session.scalar(select(func.count(FileAttachment.id))) or 0

    return AdminStats(
        total_users=user_count,
        total_channels=channel_count,
        total_messages=message_count,
        total_files=file_count,
    )
