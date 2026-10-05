from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReadState(Base):
    __tablename__ = "read_states"
    __table_args__ = (
        UniqueConstraint("workspace_id", "channel_id", "user_id", name="uq_read_states_workspace_channel_user"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id"), nullable=False, index=True)
    channel_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    last_read_sequence: Mapped[int] = mapped_column(default=0, nullable=False)
    last_read_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
