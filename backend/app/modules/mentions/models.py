from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Mention(Base):
    __tablename__ = "mentions"
    __table_args__ = (
        UniqueConstraint("organization_id", "workspace_id", "message_id", "mentioned_user_id", name="uq_mentions_org_workspace_message_user"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    message_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    mentioned_user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    mention_type: Mapped[str] = mapped_column(String(32), default="user", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
