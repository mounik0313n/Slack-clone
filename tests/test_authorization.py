from __future__ import annotations

from app.core.permissions.authorization import has_permission, require_permission
from app.core.tenancy.context import ensure_tenant_boundaries


def test_admin_has_workspace_manage_permission() -> None:
    claims = {"role": "admin"}
    assert has_permission(claims, "workspace.manage") is True


def test_member_cannot_manage_workspace() -> None:
    claims = {"role": "member"}
    assert has_permission(claims, "workspace.manage") is False


def test_explicit_permission_is_applied() -> None:
    claims = {"permissions": ["channel.create"]}
    assert has_permission(claims, "channel.create") is True


def test_require_permission_raises() -> None:
    claims = {"role": "member"}
    try:
        require_permission(claims, "workspace.manage")
        raise AssertionError("Expected PermissionError")
    except PermissionError:
        pass


def test_tenant_boundaries_enforce_workspace_match() -> None:
    claims = {"workspace_id": "ws-123", "organization_id": "org-123"}
    ensure_tenant_boundaries(claims, workspace_id="ws-123")
    try:
        ensure_tenant_boundaries(claims, workspace_id="ws-456")
        raise AssertionError("Expected PermissionError")
    except PermissionError:
        pass
