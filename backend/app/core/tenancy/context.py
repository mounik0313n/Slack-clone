from __future__ import annotations

from typing import Any


def resolve_tenant_context(claims: dict[str, Any]) -> dict[str, str | None]:
    return {
        "organization_id": claims.get("organization_id"),
        "workspace_id": claims.get("workspace_id"),
        "user_id": claims.get("sub"),
    }


def ensure_tenant_boundaries(claims: dict[str, Any], *, organization_id: str | None = None, workspace_id: str | None = None) -> None:
    context = resolve_tenant_context(claims)
    if organization_id and context.get("organization_id") and organization_id != context["organization_id"]:
        raise PermissionError("organization mismatch")
    if workspace_id and context.get("workspace_id") and workspace_id != context["workspace_id"]:
        raise PermissionError("workspace mismatch")
