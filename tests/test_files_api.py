from __future__ import annotations

import io
from datetime import datetime, timezone
import pytest
from fastapi import HTTPException, UploadFile

from app.modules.files.models import FileAttachment
from app.modules.files.router import get_file_metadata_endpoint, upload_file_endpoint


class MockFileSession:
    def __init__(self, files: dict[str, FileAttachment] | None = None) -> None:
        self.files = files or {}
        self.added = []

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, FileAttachment):
            self.files[obj.id] = obj

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass

    async def get(self, model, ident):
        if model is FileAttachment:
            return self.files.get(ident)
        return None


@pytest.mark.asyncio
async def test_upload_file_endpoint_success() -> None:
    session = MockFileSession()
    file_bytes = b"Hello, this is a test report file content."
    upload_file = UploadFile(
        file=io.BytesIO(file_bytes),
        filename="report.pdf",
        headers={"content-type": "application/pdf"},
    )

    response = await upload_file_endpoint(
        file=upload_file,
        workspace_id="ws-default",
        session=session,
        current_user={"user_id": "user-uploader-1", "workspace_id": "ws-default", "permissions": ["message.create"]},
    )

    assert response.filename == "report.pdf"
    assert response.content_type == "application/pdf"
    assert response.size_bytes == len(file_bytes)
    assert response.download_url == f"/api/v1/files/{response.id}"
    assert len(session.added) == 1


@pytest.mark.asyncio
async def test_upload_file_size_limit_rejection() -> None:
    session = MockFileSession()
    # Emulate payload exceeding 50MB
    oversized_bytes = b"0" * (51 * 1024 * 1024)
    upload_file = UploadFile(
        file=io.BytesIO(oversized_bytes),
        filename="huge.bin",
        headers={"content-type": "application/octet-stream"},
    )

    with pytest.raises(HTTPException) as exc_info:
        await upload_file_endpoint(
            file=upload_file,
            workspace_id="ws-default",
            session=session,
            current_user={"user_id": "user-1", "workspace_id": "ws-default", "permissions": ["message.create"]},
        )
    assert exc_info.value.status_code == 413


@pytest.mark.asyncio
async def test_get_file_metadata_found_and_not_found() -> None:
    attachment = FileAttachment(
        id="file-123",
        workspace_id="ws-default",
        uploader_id="user-1",
        filename="spec.json",
        content_type="application/json",
        size_bytes=100,
        storage_key="uploads/spec.json",
        created_at=datetime.now(timezone.utc),
    )
    session = MockFileSession(files={"file-123": attachment})
    caller = {"user_id": "user-1", "workspace_id": "ws-default", "permissions": ["message.read"]}

    meta = await get_file_metadata_endpoint("file-123", session=session, current_user=caller)
    assert meta.id == "file-123"
    assert meta.filename == "spec.json"

    with pytest.raises(HTTPException) as exc_info:
        await get_file_metadata_endpoint("non-existent-id", session=session, current_user=caller)
    assert exc_info.value.status_code == 404
