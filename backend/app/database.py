from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

connect_args = {"ssl": True} if settings.database_use_ssl else {}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })


engine = create_async_engine(settings.database_url, echo=settings.debug, future=True, connect_args=connect_args)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def seed_defaults() -> None:
    async with AsyncSessionLocal() as session:
        try:
            from datetime import datetime, timezone
            from sqlalchemy import select
            from app.modules.channels.models import Channel
            from app.modules.organizations.models import Organization
            from app.modules.workspaces.models import Workspace, WorkspaceMember

            res = await session.execute(select(Organization).limit(1))
            if not res.scalars().first():
                org = Organization(id="org-default", name="Acme Corp", slug="acme-corp", created_at=datetime.now(timezone.utc))
                session.add(org)
                user = User(id="user-1", email="user1@example.com", username="user-1", display_name="User One", is_active=True, email_verified=True)
                session.add(user)
                ws = Workspace(id="ws-default", organization_id="org-default", name="General", slug="general", created_at=datetime.now(timezone.utc))
                session.add(ws)
                wm = WorkspaceMember(id="wm-1", workspace_id="ws-default", user_id="user-1", role="admin", joined_at=datetime.now(timezone.utc))
                session.add(wm)
                ch1 = Channel(id="ch-general", workspace_id="ws-default", name="general", topic="Company-wide announcements and team chatter", is_private=False, is_archived=False)
                ch2 = Channel(id="ch-random", workspace_id="ws-default", name="random", topic="Random chats, watercooler banter, and fun", is_private=False, is_archived=False)
                session.add(ch1)
                session.add(ch2)
                await session.commit()
        except Exception:
            await session.rollback()


async def create_db_and_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_defaults()

