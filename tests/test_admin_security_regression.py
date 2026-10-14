from __future__ import annotations

import json
from datetime import datetime, timezone
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import create_token
from app.database import Base
from app.main import app
from app.modules.admin.models import AuditLog
from app.modules.admin.router import get_admin_stats, get_audit_logs, get_members, update_member_role
from app.modules.admin.schemas import MemberRoleUpdate
from app.modules.auth.models import User
from app.modules.auth.service import revoke_token
from app.modules.workspaces.models import Workspace, WorkspaceMember


class MockSessionWithCommitTracking:
    def __init__(
        self,
        users: dict[str, User] | None = None,
        members: dict[str, WorkspaceMember] | None = None,
        audit_logs: list[AuditLog] | None = None,
    ) -> None:
        self.users = users or {}
        self.members = members or {}
        self.audit_logs = audit_logs or []
        self.committed = False
        self.refreshed = False

    def add(self, obj):
        if isinstance(obj, AuditLog):
            self.audit_logs.append(obj)
        elif isinstance(obj, WorkspaceMember):
            self.members[f"{obj.workspace_id}:{obj.user_id}"] = obj

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        self.refreshed = True

    async def scalar(self, statement):
        # Handle count or lookup queries
        statement_str = str(statement).lower()
        if "count" in statement_str:
            if "workspace_members" in statement_str:
                return len([m for m in self.members.values() if m.role == "admin"])
            return 1
        for key, member in self.members.items():
            return member
        return None

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

            def all(self):
                # For (User, role) tuples
                return self._data

        statement_str = str(statement).lower()
        if "audit_logs" in statement_str:
            return MockResult(self.audit_logs)
        # Users join
        rows = []
        for key, mem in self.members.items():
            if ":" in key:
                ws_id, u_id = key.split(":", 1)
            else:
                u_id = key
            user = self.users.get(u_id)
            if user:
                rows.append((user, mem.role))
        return MockResult(rows)


client = TestClient(app)


def test_unauthenticated_admin_endpoints_reject_with_401() -> None:
    # 1. Audit logs
    res1 = client.get("/api/v1/admin/audit-logs")
    assert res1.status_code == 401

    # 2. Members
    res2 = client.get("/api/v1/admin/members")
    assert res2.status_code == 401

    # 3. Role update
    res3 = client.patch("/api/v1/admin/members/user-1/role", json={"role": "admin"})
    assert res3.status_code == 401

    # 4. Stats
    res4 = client.get("/api/v1/admin/stats")
    assert res4.status_code == 401


def test_invalid_and_revoked_token_reject_admin_endpoints() -> None:
    # 1. Invalid signature token
    res1 = client.get("/api/v1/admin/members", headers={"Authorization": "Bearer invalid.garbage.jwt"})
    assert res1.status_code == 401

    # 2. Revoked token
    revocable_token = create_token("user-admin-1", token_type="access", role="admin", permissions=["member.read"])
    revoke_token(revocable_token)
    res2 = client.get("/api/v1/admin/members", headers={"Authorization": f"Bearer {revocable_token}"})
    assert res2.status_code == 401


@pytest.mark.asyncio
async def test_member_enumeration_prevention_scoped_to_workspace() -> None:
    u1 = User(id="user-ws1", email="ws1@example.com", username="u1", display_name="User WS1")
    u2 = User(id="user-ws2", email="ws2@example.com", username="u2", display_name="User WS2")
    m1 = WorkspaceMember(id="wm-1", workspace_id="ws-alpha", user_id="user-ws1", role="member")

    # Only ws-alpha member is in members dict for ws-alpha
    session = MockSessionWithCommitTracking(users={"user-ws1": u1, "user-ws2": u2}, members={"ws-alpha:user-ws1": m1})

    admin_caller = {"user_id": "admin-1", "workspace_id": "ws-alpha", "role": "admin", "permissions": ["member.read"]}
    members = await get_members(workspace_id="ws-alpha", session=session, current_user=admin_caller)

    assert len(members) == 1
    assert members[0]["id"] == "user-ws1"
    # user-ws2 from another workspace is NOT present
    assert not any(m["id"] == "user-ws2" for m in members)


@pytest.mark.asyncio
async def test_unauthorized_role_change_and_privilege_escalation() -> None:
    session = MockSessionWithCommitTracking()

    # Regular member caller attempting to grant admin role
    member_caller = {"user_id": "member-1", "workspace_id": "ws-default", "role": "member", "permissions": ["workspace.manage"]}
    with pytest.raises(HTTPException) as exc_info:
        await update_member_role(
            user_id="target-1",
            payload=MemberRoleUpdate(role="admin"),
            workspace_id="ws-default",
            session=session,
            current_user=member_caller,
        )
    assert exc_info.value.status_code == 403

    # Invalid role attempt
    admin_caller = {"user_id": "admin-1", "workspace_id": "ws-default", "role": "admin", "permissions": ["workspace.manage"]}
    with pytest.raises(HTTPException) as exc_info:
        await update_member_role(
            user_id="target-1",
            payload=MemberRoleUpdate(role="super_god_mode"),
            workspace_id="ws-default",
            session=session,
            current_user=admin_caller,
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_persisted_role_change_and_audit_log_commit() -> None:
    u = User(id="user-to-promote", email="promote@example.com", username="p", display_name="Promote")
    wm = WorkspaceMember(id="wm-p", workspace_id="ws-default", user_id="user-to-promote", role="member")
    session = MockSessionWithCommitTracking(users={"user-to-promote": u}, members={"ws-default:user-to-promote": wm})

    admin_caller = {"user_id": "admin-1", "workspace_id": "ws-default", "role": "admin", "permissions": ["workspace.manage"]}
    res = await update_member_role(
        user_id="user-to-promote",
        payload=MemberRoleUpdate(role="admin"),
        workspace_id="ws-default",
        session=session,
        current_user=admin_caller,
    )

    assert res["status"] == "ok"
    assert res["role"] == "admin"
    assert wm.role == "admin"
    assert session.committed is True

    # Validate genuine AuditLog row creation in session
    assert len(session.audit_logs) == 1
    audit = session.audit_logs[0]
    assert audit.action == "member.role_updated"
    assert audit.actor_id == "admin-1"
    assert audit.target_id == "user-to-promote"
    details = json.loads(audit.details)
    assert details["old_role"] == "member"
    assert details["new_role"] == "admin"
