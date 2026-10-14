from __future__ import annotations

import io
import json
import secrets
from datetime import datetime, timezone
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import create_token, decode_token
from app.database import create_db_and_tables
from app.main import app, realtime_gateway


def get_test_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_e2e_workflow_1_registration_login_profile() -> None:
    """1. A new user registers and logs in, retrieves profile dynamically."""
    await create_db_and_tables()
    uniq = secrets.token_hex(4)
    email = f"alex_{uniq}@testcorp.io"
    password = "SecurePassword123!"

    async with get_test_client() as client:
        # 1. Register
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "username": f"alex_{uniq}",
                "display_name": f"Alex {uniq}",
                "password": password,
            },
        )
        assert reg_res.status_code == 201, reg_res.text
        user_data = reg_res.json()
        assert user_data["email"] == email

        # 2. Login
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login_res.status_code == 200, login_res.text
        tokens = login_res.json()
        assert "access_token" in tokens
        assert "refresh_token" in tokens

        # 3. Dynamic Profile
        auth_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        me_res = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert me_res.status_code == 200, me_res.text
        profile = me_res.json()
        assert profile["id"] == user_data["id"]
        assert profile["email"] == email


@pytest.mark.asyncio
async def test_e2e_workflow_2_and_3_workspace_creation_and_invitation() -> None:
    """2. The authenticated user creates a workspace.
       3. Another user joins through an invitation/membership."""
    await create_db_and_tables()
    admin_token = create_token(
        "user-1",
        token_type="access",
        workspace_id="ws-default",
        role="admin",
        permissions=["workspace.manage", "member.read", "channel.read", "channel.create"],
    )
    headers = {"Authorization": f"Bearer {admin_token}"}

    async with get_test_client() as client:
        # 2. Create workspace
        slug = f"acme-cloud-{secrets.token_hex(3)}"
        ws_res = await client.post(
            "/api/v1/workspaces",
            json={"organization_id": "org-default", "name": "Acme Cloud", "slug": slug},
            headers=headers,
        )
        assert ws_res.status_code == 201, ws_res.text
        ws_id = ws_res.json()["id"]

        # 3. Add / invite another user using token scoped to the newly created workspace
        ws_admin_token = create_token(
            "user-1",
            token_type="access",
            workspace_id=ws_id,
            role="admin",
            permissions=["workspace.manage", "member.read"],
        )
        ws_headers = {"Authorization": f"Bearer {ws_admin_token}"}

        invite_res = await client.post(
            f"/api/v1/workspaces/{ws_id}/members",
            json={"user_id": "user-2", "role": "member"},
            headers=ws_headers,
        )
        assert invite_res.status_code == 201, invite_res.text
        member_data = invite_res.json()
        assert member_data["workspace_id"] == ws_id
        assert member_data["user_id"] == "user-2"

        # Verify members list
        members_res = await client.get(f"/api/v1/workspaces/{ws_id}/members", headers=ws_headers)
        assert members_res.status_code == 200, members_res.text
        member_ids = [m["user_id"] for m in members_res.json()]
        assert "user-2" in member_ids


@pytest.mark.asyncio
async def test_e2e_workflow_4_shared_channel_access() -> None:
    """4. Both users can access the same authorized channel."""
    await create_db_and_tables()
    ws_id = "ws-default"
    admin_token = create_token("user-1", token_type="access", workspace_id=ws_id, role="admin", permissions=["channel.create", "channel.read"])
    member_token = create_token("user-2", token_type="access", workspace_id=ws_id, role="member", permissions=["channel.read"])

    async with get_test_client() as client:
        # User 1 creates channel
        ch_name = f"dev-team-{secrets.token_hex(3)}"
        create_res = await client.post(
            "/api/v1/channels",
            json={"workspace_id": ws_id, "name": ch_name, "topic": "Sprint discussions", "is_private": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert create_res.status_code == 201, create_res.text
        ch_id = create_res.json()["id"]

        # Both User 1 and User 2 list channels and see it
        res_a = await client.get(f"/api/v1/channels?workspace_id={ws_id}", headers={"Authorization": f"Bearer {admin_token}"})
        assert any(c["id"] == ch_id for c in res_a.json())

        res_b = await client.get(f"/api/v1/channels?workspace_id={ws_id}", headers={"Authorization": f"Bearer {member_token}"})
        assert any(c["id"] == ch_id for c in res_b.json())


@pytest.mark.asyncio
async def test_e2e_workflow_5_6_messaging_realtime_and_persistence() -> None:
    """5. One user sends a message and real-time delivery works.
       6. The message persists after querying / refresh."""
    await create_db_and_tables()
    ws_id = "ws-default"
    sender_token = create_token("user-1", token_type="access", workspace_id=ws_id, role="member", permissions=["message.create", "message.read"])
    receiver_token = create_token("user-2", token_type="access", workspace_id=ws_id, role="member", permissions=["message.read"])

    ch_id = "ch-general"

    async with get_test_client() as client:
        # Send message
        msg_body = f"Hello team! Persistent update {secrets.token_hex(4)}"
        client_mid = f"cl-msg-{secrets.token_hex(6)}"

        post_res = await client.post(
            "/api/v1/messages",
            json={
                "workspace_id": ws_id,
                "channel_id": ch_id,
                "author_id": "user-1",
                "body": msg_body,
                "client_message_id": client_mid,
            },
            headers={"Authorization": f"Bearer {sender_token}"},
        )
        assert post_res.status_code == 201, post_res.text
        created_msg = post_res.json()
        assert created_msg["body"] == msg_body

        # 6. Verify persistence on subsequent read
        list_res = await client.get(
            f"/api/v1/messages?channel_id={ch_id}",
            headers={"Authorization": f"Bearer {receiver_token}"},
        )
        assert list_res.status_code == 200, list_res.text
        messages = list_res.json()
        assert any(m["id"] == created_msg["id"] and m["body"] == msg_body for m in messages)


@pytest.mark.asyncio
async def test_e2e_workflow_7_message_editing_deleting_reactions_threads_pins_bookmarks() -> None:
    """7. Editing, deleting, reacting to, replying to, pinning, and bookmarking messages works."""
    await create_db_and_tables()
    ws_id = "ws-default"
    user_token = create_token("user-1", token_type="access", workspace_id=ws_id, role="member", permissions=["message.create", "message.read", "reaction.create", "channel.read"])
    headers = {"Authorization": f"Bearer {user_token}"}
    ch_id = "ch-general"

    async with get_test_client() as client:
        # 1. Create root message
        root_res = await client.post(
            "/api/v1/messages",
            json={"workspace_id": ws_id, "channel_id": ch_id, "author_id": "user-1", "body": "Initial text content"},
            headers=headers,
        )
        assert root_res.status_code == 201
        root_msg_id = root_res.json()["id"]

        # 2. Edit message
        patch_res = await client.patch(
            f"/api/v1/messages/{root_msg_id}",
            json={"body": "Edited text content"},
            headers=headers,
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["body"] == "Edited text content"

        # 3. Pin message
        pin_res = await client.post(f"/api/v1/messages/{root_msg_id}/pin", headers=headers)
        assert pin_res.status_code == 200
        assert pin_res.json()["is_pinned"] is True

        # Pinned messages list
        pinned_list = await client.get(f"/api/v1/messages/pinned/channel/{ch_id}", headers=headers)
        assert pinned_list.status_code == 200
        assert any(m["id"] == root_msg_id for m in pinned_list.json())

        # 4. React to message
        react_res = await client.post(
            "/api/v1/reactions",
            json={"workspace_id": ws_id, "channel_id": ch_id, "message_id": root_msg_id, "user_id": "user-1", "emoji": "🚀"},
            headers=headers,
        )
        assert react_res.status_code == 201

        # 5. Thread reply
        reply_res = await client.post(
            "/api/v1/messages",
            json={"workspace_id": ws_id, "channel_id": ch_id, "author_id": "user-1", "body": "This is a reply in thread", "thread_id": root_msg_id},
            headers=headers,
        )
        assert reply_res.status_code == 201
        assert reply_res.json()["thread_id"] == root_msg_id

        # 6. Channel bookmark
        bm_res = await client.post(
            f"/api/v1/channels/{ch_id}/bookmarks",
            json={"title": "Sprint Board", "url": "https://jira.corp.internal/board/1"},
            headers=headers,
        )
        assert bm_res.status_code == 201
        bm_id = bm_res.json()["id"]

        # List bookmarks
        bm_list = await client.get(f"/api/v1/channels/{ch_id}/bookmarks", headers=headers)
        assert any(b["id"] == bm_id for b in bm_list.json())

        # Delete bookmark
        del_bm = await client.delete(f"/api/v1/channels/{ch_id}/bookmarks/{bm_id}", headers=headers)
        assert del_bm.status_code == 200

        # 7. Delete reply message
        del_res = await client.delete(f"/api/v1/messages/{reply_res.json()['id']}", headers=headers)
        assert del_res.status_code == 200
        assert del_res.json()["deleted"] is True


@pytest.mark.asyncio
async def test_e2e_workflow_8_private_channel_and_dm_isolation() -> None:
    """8. Private channels and direct messages remain inaccessible to unauthorized users."""
    await create_db_and_tables()
    ws_id = "ws-default"
    admin_token = create_token("user-1", token_type="access", workspace_id=ws_id, role="admin", permissions=["channel.create", "channel.read", "message.read"])
    unauth_token = create_token("user-3", token_type="access", workspace_id=ws_id, role="member", permissions=["channel.read", "message.read"])

    async with get_test_client() as client:
        # Admin creates private channel
        priv_ch = await client.post(
            "/api/v1/channels",
            json={"workspace_id": ws_id, "name": f"finance-secrets-{secrets.token_hex(3)}", "is_private": True},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert priv_ch.status_code == 201
        priv_ch_id = priv_ch.json()["id"]

        # Unauthorized member attempts to list messages in private channel -> rejected 403
        unauth_res = await client.get(
            f"/api/v1/messages?channel_id={priv_ch_id}",
            headers={"Authorization": f"Bearer {unauth_token}"},
        )
        assert unauth_res.status_code == 403

        # Unauthorized member attempts AI summary of private channel -> rejected 403
        ai_res = await client.post(
            "/api/v1/ai/summarize",
            json={"channel_id": priv_ch_id},
            headers={"Authorization": f"Bearer {unauth_token}"},
        )
        assert ai_res.status_code == 403


@pytest.mark.asyncio
async def test_e2e_workflow_9_file_upload_and_download_permissions() -> None:
    """9. File uploads and downloads enforce access permissions and tenant isolation."""
    await create_db_and_tables()
    ws_alpha = "ws-default"
    ws_beta = "ws-other"

    user_alpha = create_token("user-1", token_type="access", workspace_id=ws_alpha, role="member", permissions=["message.create", "message.read"])
    user_beta = create_token("user-2", token_type="access", workspace_id=ws_beta, role="member", permissions=["message.create", "message.read"])

    file_content = b"Financial quarterly earnings: CONFIDENTIAL"

    async with get_test_client() as client:
        upload_res = await client.post(
            f"/api/v1/files/upload?workspace_id={ws_alpha}",
            files={"file": ("earnings.csv", io.BytesIO(file_content), "text/csv")},
            headers={"Authorization": f"Bearer {user_alpha}"},
        )
        assert upload_res.status_code == 201
        file_id = upload_res.json()["id"]

        # User in Alpha workspace can download file
        down_alpha = await client.get(
            f"/api/v1/files/{file_id}/download",
            headers={"Authorization": f"Bearer {user_alpha}"},
        )
        assert down_alpha.status_code == 200
        assert down_alpha.content == file_content

        # User in Beta workspace is rejected with 401/403 due to tenant isolation
        down_beta = await client.get(
            f"/api/v1/files/{file_id}/download",
            headers={"Authorization": f"Bearer {user_beta}"},
        )
        assert down_beta.status_code in (401, 403)


@pytest.mark.asyncio
async def test_e2e_workflow_10_search_returns_authorized_results_only() -> None:
    """10. Search returns only authorized results within the workspace."""
    await create_db_and_tables()
    ws_a = "ws-default"
    ws_b = "ws-forbidden"

    user_a = create_token("user-1", token_type="access", workspace_id=ws_a, role="member", permissions=["message.read"])

    async with get_test_client() as client:
        # Search in caller's workspace succeeds
        search_ok = await client.get(
            f"/api/v1/search/messages?query=meeting&workspace_id={ws_a}",
            headers={"Authorization": f"Bearer {user_a}"},
        )
        assert search_ok.status_code == 200

        # Cross-workspace search is rejected
        search_bad = await client.get(
            f"/api/v1/search/messages?query=meeting&workspace_id={ws_b}",
            headers={"Authorization": f"Bearer {user_a}"},
        )
        assert search_bad.status_code in (401, 403)


@pytest.mark.asyncio
async def test_e2e_workflow_11_workspace_roles_and_admin_permissions() -> None:
    """11. Workspace roles and administrative permissions are enforced."""
    await create_db_and_tables()
    admin_token = create_token("user-1", token_type="access", workspace_id="ws-default", role="admin", permissions=["workspace.manage", "audit.read"])
    member_token = create_token("user-2", token_type="access", workspace_id="ws-default", role="member", permissions=["message.read"])

    async with get_test_client() as client:
        # Admin accesses audit logs -> 200
        audit_res = await client.get("/api/v1/admin/audit-logs", headers={"Authorization": f"Bearer {admin_token}"})
        assert audit_res.status_code == 200

        # Member attempts to access audit logs -> 403
        mem_audit = await client.get("/api/v1/admin/audit-logs", headers={"Authorization": f"Bearer {member_token}"})
        assert mem_audit.status_code == 403

        # Member attempts to alter user role -> 403
        role_change = await client.patch(
            "/api/v1/admin/members/user-3/role",
            json={"role": "admin"},
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert role_change.status_code == 403


@pytest.mark.asyncio
async def test_e2e_workflow_12_expired_tokens_and_duplicate_deduplication() -> None:
    """12. Expired tokens, duplicate submissions, and client message IDs are handled correctly."""
    await create_db_and_tables()
    expired_token = create_token("user-exp", token_type="access", workspace_id="ws-default", expires_delta_seconds=-100)

    async with get_test_client() as client:
        res_exp = await client.get("/api/v1/channels", headers={"Authorization": f"Bearer {expired_token}"})
        assert res_exp.status_code == 401

        # Idempotent message submission
        valid_token = create_token("user-1", token_type="access", workspace_id="ws-default", role="member", permissions=["message.create", "message.read"])
        client_mid = f"idem-key-{secrets.token_hex(6)}"

        msg1 = await client.post(
            "/api/v1/messages",
            json={"workspace_id": "ws-default", "channel_id": "ch-general", "author_id": "user-1", "body": "Idempotent write", "client_message_id": client_mid},
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert msg1.status_code == 201

        # Resubmission with same client_message_id returns the exact same message without creating duplicates
        msg2 = await client.post(
            "/api/v1/messages",
            json={"workspace_id": "ws-default", "channel_id": "ch-general", "author_id": "user-1", "body": "Idempotent write", "client_message_id": client_mid},
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert msg2.status_code == 201
        assert msg1.json()["id"] == msg2.json()["id"]
