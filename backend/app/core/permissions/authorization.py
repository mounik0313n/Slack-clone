from __future__ import annotations

from typing import Any

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {
        "workspace.read",
        "workspace.manage",
        "channel.read",
        "channel.create",
        "channel.update",
        "channel.delete",
        "message.read",
        "message.create",
        "message.update",
        "message.delete",
        "member.read",
        "member.invite",
        "audit.read",
    },
    "member": {
        "workspace.read",
        "channel.read",
        "message.read",
        "message.create",
        "member.read",
    },
}


def get_user_permissions(claims: dict[str, Any]) -> set[str]:
    permissions: set[str] = set()
    roles = claims.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    if claims.get("role"):
        roles = [*roles, claims["role"]]

    for role in roles:
        permissions |= ROLE_PERMISSIONS.get(str(role), set())

    explicit_permissions = claims.get("permissions") or []
    if isinstance(explicit_permissions, str):
        explicit_permissions = [explicit_permissions]
    permissions |= set(explicit_permissions)
    return permissions


def has_permission(claims: dict[str, Any], permission: str) -> bool:
    if claims.get("is_admin") is True:
        return True
    return permission in get_user_permissions(claims)


def require_permission(claims: dict[str, Any], permission: str) -> None:
    if not has_permission(claims, permission):
        raise PermissionError(f"Missing permission: {permission}")
