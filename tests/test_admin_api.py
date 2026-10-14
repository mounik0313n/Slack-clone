from __future__ import annotations

from datetime import datetime, timezone
import pytest
from fastapi import HTTPException

from app.modules.admin.models import AuditLog
from app.modules.admin.router import get_admin_stats, get_audit_logs, update_member_role
from app.modules.admin.schemas import MemberRoleUpdate
from app.modules.auth.models import User
from app.modules.workspaces.models import WorkspaceMember


class MockAdminSession:
    def __init__(self, users: dict[str, User] | None = None, members: dict[str, WorkspaceMember] | None = None) -> None:
        self.users = users or {}
        self.members = members or {}
        self.audit_logs = [
            AuditLog(id="a1", workspace_id="ws-default", actor_id="user-1", action="workspace.created", details="{}", created_at=datetime.now(timezone.utc)),
            AuditLog(id="a2", workspace_id="ws-default", actor_id="user-1", action="channel.created", details="{}", created_at=datetime.now(timezone.utc)),
        ]

    def add(self, obj):
        if isinstance(obj, AuditLog):
            self.audit_logs.append(obj)

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass

    async def get(self, model, ident):
        if model is User:
            return self.users.get(ident)
        return None

    async def scalar(self, statement):
        stmt_str = str(statement).lower()
        if "workspace_members" in stmt_str and "user_id" in stmt_str:
            for m in self.members.values():
                return m
            return None
        return 5

    async def execute(self, statement):
        class MockResult:
            def __init__(self, data):
                self._data = data

            def scalars(self):
                class MockScalars:
                    def __init__(self, data):
                        self._data = data

                    def all(self):
                        return self._data

                return MockScalars(self._data)

        return MockResult(self.audit_logs)


@pytest.mark.asyncio
async def test_audit_logs_permission_enforcement() -> None:
    session = MockAdminSession()
    # User with audit.read permission succeeds
    admin_user = {"user_id": "user-admin", "workspace_id": "ws-default", "role": "admin", "permissions": ["audit.read"]}
    logs = await get_audit_logs(workspace_id="ws-default", session=session, current_user=admin_user)
    assert len(logs) >= 2

    # Regular member lacking audit.read permission is blocked
    member_user = {"user_id": "user-member", "workspace_id": "ws-default", "role": "member", "permissions": []}
    with pytest.raises(PermissionError):
        await get_audit_logs(workspace_id="ws-default", session=session, current_user=member_user)


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
    target_member = WorkspaceMember(
        id="wm-target",
        workspace_id="ws-default",
        user_id="user-target-1",
        role="member",
    )
    session = MockAdminSession(
        users={target_user.id: target_user},
        members={target_member.user_id: target_member},
    )

    admin_user = {"user_id": "user-admin", "workspace_id": "ws-default", "role": "admin", "permissions": ["workspace.manage"]}
    res = await update_member_role(
        user_id="user-target-1",
        payload=MemberRoleUpdate(role="admin"),
        workspace_id="ws-default",
        session=session,
        current_user=admin_user,
    )
    assert res["status"] == "ok"
    assert res["role"] == "admin"

    # Member user cannot update roles (forbidden)
    member_user = {"user_id": "user-member", "workspace_id": "ws-default", "role": "member", "permissions": ["workspace.manage"]}
    with pytest.raises(HTTPException) as exc_info:
        await update_member_role(
            user_id="user-target-1",
            payload=MemberRoleUpdate(role="admin"),
            workspace_id="ws-default",
            session=session,
            current_user=member_user,
        )
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_get_admin_stats_aggregation() -> None:
    session = MockAdminSession()
    admin_user = {"user_id": "user-admin", "workspace_id": "ws-default", "role": "admin", "permissions": ["audit.read"]}
    stats = await get_admin_stats(workspace_id="ws-default", session=session, current_user=admin_user)
    assert stats.total_users == 5
    assert stats.total_channels == 5
    assert stats.total_messages == 5
    assert stats.total_files == 5
