from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class FileUploadResponse(BaseModel):
    id: str
    filename: str
    content_type: str
    size_bytes: int
    download_url: str
    created_at: datetime


class FileRead(BaseModel):
    id: str
    workspace_id: str
    uploader_id: str
    filename: str
    content_type: str
    size_bytes: int
    download_url: str
    created_at: datetime
