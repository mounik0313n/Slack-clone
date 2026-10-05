from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("workspace_id", "channel_id", "client_message_id", name="uq_messages_workspace_channel_client_message_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    channel_id: Mapped[str] = mapped_column(String(36), ForeignKey("channels.id"), nullable=False, index=True)
    author_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(default=1, nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    thread_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    client_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
