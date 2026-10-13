from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class MemberRoleUpdate(BaseModel):
    role: str  # "admin", "member", "guest"


class AuditLogItem(BaseModel):
    id: str
    action: str
    actor_id: str
    target_id: str | None = None
    timestamp: datetime
    details: dict = {}


class AdminStats(BaseModel):
    total_users: int
    total_channels: int
    total_messages: int
    total_files: int
