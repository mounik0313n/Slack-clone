from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.authorization import require_permission
from app.core.tenancy.context import ensure_tenant_boundaries
from app.dependencies import get_current_user, get_db
from app.modules.files.models import FileAttachment
from app.modules.files.schemas import FileRead, FileUploadResponse

router = APIRouter(prefix="/files", tags=["files"])

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50MB limit


@router.post("/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file_endpoint(
    file: UploadFile = File(...),
    workspace_id: str = "ws-default",
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> FileUploadResponse:
    # 1. Require message.create permission & verify tenant boundaries
    require_permission(current_user, "message.create")
    ensure_tenant_boundaries(current_user, workspace_id=workspace_id)

    content = await file.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="File exceeds maximum 50MB size limit")

    content_type = file.content_type or "application/octet-stream"
    safe_filename = os.path.basename(file.filename or "upload.bin")
    file_id = f"file-{secrets.token_hex(8)}"
    uploader_id = current_user["user_id"]
    storage_key = f"uploads/{workspace_id}/{file_id}/{safe_filename}"

    # Save to local storage
    try:
        abs_target_dir = os.path.join(os.getcwd(), "uploads", workspace_id, file_id)
        os.makedirs(abs_target_dir, exist_ok=True)
        with open(os.path.join(abs_target_dir, safe_filename), "wb") as f:
            f.write(content)
    except Exception:
        pass

    attachment = FileAttachment(
        id=file_id,
        workspace_id=workspace_id,
        uploader_id=uploader_id,
        filename=safe_filename,
        content_type=content_type,
        size_bytes=len(content),
        storage_key=storage_key,
        created_at=datetime.now(timezone.utc),
    )
    session.add(attachment)
    await session.commit()
    await session.refresh(attachment)

    return FileUploadResponse(
        id=attachment.id,
        filename=attachment.filename,
        content_type=attachment.content_type,
        size_bytes=attachment.size_bytes,
        download_url=f"/api/v1/files/{attachment.id}",
        created_at=attachment.created_at,
    )


@router.get("/{file_id}", response_model=FileRead)
async def get_file_metadata_endpoint(
    file_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> FileRead:
    require_permission(current_user, "message.read")

    attachment = await session.get(FileAttachment, file_id)
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # Enforce workspace isolation on file downloads
    ensure_tenant_boundaries(current_user, workspace_id=attachment.workspace_id)

    return FileRead(
        id=attachment.id,
        workspace_id=attachment.workspace_id,
        uploader_id=attachment.uploader_id,
        filename=attachment.filename,
        content_type=attachment.content_type,
        size_bytes=attachment.size_bytes,
        download_url=f"/api/v1/files/{attachment.id}",
        created_at=attachment.created_at,
    )


@router.get("/{file_id}/download")
async def download_file_endpoint(
    file_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> Response:
    require_permission(current_user, "message.read")

    attachment = await session.get(FileAttachment, file_id)
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    ensure_tenant_boundaries(current_user, workspace_id=attachment.workspace_id)

    abs_path = os.path.join(os.getcwd(), attachment.storage_key)
    file_bytes = b""
    if os.path.exists(abs_path):
        with open(abs_path, "rb") as f:
            file_bytes = f.read()

    return Response(
        content=file_bytes,
        media_type=attachment.content_type,
        headers={"Content-Disposition": f'attachment; filename="{attachment.filename}"'},
    )

