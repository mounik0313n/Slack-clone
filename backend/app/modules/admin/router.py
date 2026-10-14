from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.authorization import require_permission
from app.core.tenancy.context import ensure_tenant_boundaries
from app.dependencies import get_current_user, get_db
from app.modules.admin.models import AuditLog
from app.modules.admin.schemas import AdminStats, AuditLogItem, MemberRoleUpdate
from app.modules.auth.models import User
from app.modules.channels.models import Channel
from app.modules.files.models import FileAttachment
from app.modules.messages.models import Message
from app.modules.workspaces.models import WorkspaceMember

router = APIRouter(prefix="/admin", tags=["admin"])

VALID_ROLES = {"admin", "member", "guest"}


@router.get("/audit-logs", response_model=list[AuditLogItem])
async def get_audit_logs(
    workspace_id: str = Query("ws-default", description="Target workspace ID"),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> list[AuditLogItem]:
    require_permission(current_user, "audit.read")
    ensure_tenant_boundaries(current_user, workspace_id=workspace_id)

    result = await session.execute(
        select(AuditLog)
        .where(AuditLog.workspace_id == workspace_id)
        .order_by(AuditLog.created_at.desc())
        .limit(100)
    )
    entries = list(result.scalars().all())

    return [
        AuditLogItem(
            id=entry.id,
            action=entry.action,
            actor_id=entry.actor_id,
            target_id=entry.target_id,
            timestamp=entry.created_at,
            details=json.loads(entry.details) if entry.details else {},
        )
        for entry in entries
    ]


@router.get("/members")
async def get_members(
    workspace_id: str = Query("ws-default", description="Target workspace ID"),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    require_permission(current_user, "member.read")
    ensure_tenant_boundaries(current_user, workspace_id=workspace_id)

    # Scoped strictly to workspace_members to prevent member enumeration across tenants
    query = (
        select(User, WorkspaceMember.role)
        .join(WorkspaceMember, WorkspaceMember.user_id == User.id)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(User.display_name)
    )
    result = await session.execute(query)
    rows = list(result.all())

    return [
        {
            "id": u.id,
            "email": u.email,
            "username": u.username,
            "display_name": u.display_name,
            "role": role,
            "is_active": u.is_active,
        }
        for u, role in rows
    ]


@router.patch("/members/{user_id}/role")
async def update_member_role(
    user_id: str,
    payload: MemberRoleUpdate,
    workspace_id: str = Query("ws-default", description="Target workspace ID"),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
    # 1. Require explicit workspace.manage permission
    require_permission(current_user, "workspace.manage")

    # 2. Enforce tenant boundaries
    ensure_tenant_boundaries(current_user, workspace_id=workspace_id)

    # 3. Validate permitted roles
    if payload.role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{payload.role}'. Must be one of: {', '.join(sorted(VALID_ROLES))}",
        )

    # 4. Prevent privilege escalation: caller must be an admin
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can assign or modify member roles",
        )

    # 5. Check target user membership in the specified workspace
    member = await session.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found in this workspace",
        )

    # 6. Prevent demotion of the last administrator
    if member.role == "admin" and payload.role != "admin":
        admin_count = await session.scalar(
            select(func.count(WorkspaceMember.id)).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == "admin",
            )
        ) or 0
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the last administrator of the workspace",
            )

    # 7. Persist genuine role assignment and audit event
    old_role = member.role
    member.role = payload.role

    audit_entry = AuditLog(
        id=f"audit-{secrets.token_hex(8)}",
        workspace_id=workspace_id,
        actor_id=current_user["user_id"],
        action="member.role_updated",
        target_id=user_id,
        details=json.dumps({"old_role": old_role, "new_role": payload.role}),
        created_at=datetime.now(timezone.utc),
    )
    session.add(audit_entry)

    # Commit both changes atomically; do not return success unless it commits
    await session.commit()
    await session.refresh(member)

    return {
        "status": "ok",
        "user_id": user_id,
        "role": member.role,
        "workspace_id": workspace_id,
    }


@router.get("/stats", response_model=AdminStats)
async def get_admin_stats(
    workspace_id: str = Query("ws-default", description="Target workspace ID"),
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> AdminStats:
    require_permission(current_user, "audit.read")
    ensure_tenant_boundaries(current_user, workspace_id=workspace_id)

    user_count = await session.scalar(
        select(func.count(WorkspaceMember.id)).where(WorkspaceMember.workspace_id == workspace_id)
    ) or 0
    channel_count = await session.scalar(
        select(func.count(Channel.id)).where(Channel.workspace_id == workspace_id)
    ) or 0
    message_count = await session.scalar(
        select(func.count(Message.id)).where(Message.workspace_id == workspace_id)
    ) or 0
    file_count = await session.scalar(
        select(func.count(FileAttachment.id)).where(FileAttachment.workspace_id == workspace_id)
    ) or 0

    return AdminStats(
        total_users=user_count,
        total_channels=channel_count,
        total_messages=message_count,
        total_files=file_count,
    )
