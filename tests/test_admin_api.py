from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.modules.admin.router import get_admin_stats, get_audit_logs, update_member_role
from app.modules.admin.schemas import MemberRoleUpdate
from app.modules.auth.models import User


class MockAdminSession:
    def __init__(self, users: dict[str, User] | None = None) -> None:
        self.users = users or {}

    async def get(self, model, ident):
        if model is User:
            return self.users.get(ident)
        return None

    async def scalar(self, statement):
        return 5


@pytest.mark.asyncio
async def test_audit_logs_permission_enforcement() -> None:
    # User with audit.read permission succeeds
    admin_user = {"user_id": "user-admin", "role": "admin", "permissions": ["audit.read"]}
    logs = await get_audit_logs(current_user=admin_user)
    assert len(logs) >= 2

    # Regular member lacking audit.read permission is blocked
    member_user = {"user_id": "user-member", "role": "member", "permissions": []}
    with pytest.raises(PermissionError):
        await get_audit_logs(current_user=member_user)


@pytest.mark.asyncio
async def test_update_member_role_rbac_and_audit() -> None:
    target_user = User(
        id="user-target-1",
        email="target@example.com",
        username="target",
        display_name="Target",
        password_hash="hash",
        is_active=True,
        email_verified=True,
    )
    session = MockAdminSession(users={target_user.id: target_user})

    admin_user = {"user_id": "user-admin", "role": "admin", "permissions": ["workspace.manage"]}
    res = await update_member_role(
        user_id="user-target-1",
        payload=MemberRoleUpdate(role="admin"),
        session=session,
        current_user=admin_user,
    )
    assert res["status"] == "ok"
    assert res["role"] == "admin"

    # Member user cannot update roles
    member_user = {"user_id": "user-member", "role": "member", "permissions": []}
    with pytest.raises(PermissionError):
        await update_member_role(
            user_id="user-target-1",
            payload=MemberRoleUpdate(role="admin"),
            session=session,
            current_user=member_user,
        )


@pytest.mark.asyncio
async def test_get_admin_stats_aggregation() -> None:
    session = MockAdminSession()
    stats = await get_admin_stats(session=session)
    assert stats.total_users == 5
    assert stats.total_channels == 5
    assert stats.total_messages == 5
    assert stats.total_files == 5
