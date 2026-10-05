from __future__ import annotations

from typing import Any


def user_has_permission(claims: dict[str, Any], permission: str) -> bool:
    roles = claims.get("roles", [])
    if isinstance(roles, str):
        roles = [roles]
    if claims.get("role"):
        roles.append(claims["role"])
    return permission in {"workspace.manage", "workspace.read", "channel.read", "channel.create", "message.create"} and (
        claims.get("is_admin") is True or claims.get("role") == "admin" or permission in {"workspace.read", "channel.read", "message.create"}
    )
