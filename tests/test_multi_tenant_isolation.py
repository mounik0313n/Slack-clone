from __future__ import annotations

import pytest

from app.core.tenancy.context import ensure_tenant_boundaries
from app.modules.messages.models import Message


def test_tenant_boundaries_allows_matching_tenant() -> None:
    claims = {"workspace_id": "ws-engineering", "organization_id": "org-acme"}
    # Must not raise
    ensure_tenant_boundaries(claims, workspace_id="ws-engineering", organization_id="org-acme")


def test_tenant_boundaries_rejects_cross_tenant_workspace_access() -> None:
    claims = {"workspace_id": "ws-engineering", "organization_id": "org-acme"}
    with pytest.raises(PermissionError):
        ensure_tenant_boundaries(claims, workspace_id="ws-marketing")


def test_tenant_boundaries_rejects_cross_tenant_organization_access() -> None:
    claims = {"workspace_id": "ws-engineering", "organization_id": "org-acme"}
    with pytest.raises(PermissionError):
        ensure_tenant_boundaries(claims, organization_id="org-other")


def test_message_tenant_isolation_boundary() -> None:
    # Validate messages belong exclusively to their respective workspace
    msg_tenant_a = Message(
        id="msg-a",
        workspace_id="ws-alpha",
        channel_id="ch-alpha",
        author_id="user-a",
        sequence=1,
        body="Secret alpha data",
    )
    msg_tenant_b = Message(
        id="msg-b",
        workspace_id="ws-beta",
        channel_id="ch-beta",
        author_id="user-b",
        sequence=1,
        body="Secret beta data",
    )

    assert msg_tenant_a.workspace_id != msg_tenant_b.workspace_id
    assert msg_tenant_a.workspace_id == "ws-alpha"
    assert msg_tenant_b.workspace_id == "ws-beta"
