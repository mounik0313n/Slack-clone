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
            from app.modules.auth.models import User
            from app.modules.auth.service import ph
            from app.modules.channels.models import Channel, ChannelMember
            from app.modules.conversations.models import Conversation, ConversationMember
            from app.modules.messages.models import Message
            from app.modules.organizations.models import Organization
            from app.modules.reactions.models import Reaction
            from app.modules.workspaces.models import Workspace, WorkspaceMember

            res = await session.execute(select(Organization).limit(1))
            if not res.scalars().first():
                now = datetime.now(timezone.utc)
                org = Organization(id="org-default", name="Acme Inc", slug="acme-inc", created_at=now)
                session.add(org)

                ws = Workspace(id="ws-default", organization_id="org-default", name="Acme Inc", slug="acme-inc", created_at=now)
                session.add(ws)

                default_password_hash = ph.hash("password123")
                users_data = [
                    ("user-1", "zoe@acme.com", "zoe", "Zoe Maxwell", "admin"),
                    ("user-2", "lee@acme.com", "lee", "Lee Hao", "member"),
                    ("user-3", "lisa@acme.com", "lisa", "Lisa Dawson", "member"),
                    ("user-bot", "bot@acme.com", "acmeteam", "Acme Team", "member"),
                    ("user-slackbot", "slackbot@acme.com", "slackbot", "Slackbot AI", "member"),
                ]

                for uid, email, username, display_name, role in users_data:
                    u = User(
                        id=uid,
                        email=email,
                        username=username,
                        display_name=display_name,
                        password_hash=default_password_hash,
                        is_active=True,
                        email_verified=True,
                    )
                    session.add(u)
                    wm = WorkspaceMember(
                        id=f"wm-{uid}",
                        workspace_id="ws-default",
                        user_id=uid,
                        role=role,
                        joined_at=now,
                    )
                    session.add(wm)

                channels_data = [
                    ("ch-social-media", "social-media", "Track and coordinate social media", False),
                    ("ch-announcements", "announcements", "Company announcements", False),
                    ("ch-design-crit", "design-crit", "Design critique & reviews", True),
                    ("ch-media-and-pr", "media-and-pr", "Media and press relations", False),
                    ("ch-team-marketing", "team-marketing", "Team marketing campaigns", False),
                    ("ch-general", "general", "Company-wide announcements and team chatter", False),
                    ("ch-random", "random", "Random chats, watercooler banter, and fun", False),
                ]

                for ch_id, ch_name, topic, is_priv in channels_data:
                    ch = Channel(
                        id=ch_id,
                        workspace_id="ws-default",
                        name=ch_name,
                        topic=topic,
                        is_private=is_priv,
                        is_archived=False,
                        created_at=now,
                    )
                    session.add(ch)
                    # Add team users as members of each channel
                    for uid, _, _, _, role in users_data:
                        cm = ChannelMember(
                            id=f"cm-{ch_id}-{uid}",
                            channel_id=ch_id,
                            user_id=uid,
                            role=role,
                            joined_at=now,
                        )
                        session.add(cm)

                # Seed direct conversation between user-1 and user-2
                conv = Conversation(
                    id="conv-dm-zoe-lee",
                    workspace_id="ws-default",
                    type="dm",
                    created_by="user-1",
                    created_at=now,
                )
                session.add(conv)
                session.add(ConversationMember(id="cmem-1", conversation_id="conv-dm-zoe-lee", user_id="user-1", joined_at=now))
                session.add(ConversationMember(id="cmem-2", conversation_id="conv-dm-zoe-lee", user_id="user-2", joined_at=now))

                # Seed initial messages in ch-social-media
                seed_msgs = [
                    ("msg-sm-1", "user-bot", 1, "Event starting in 15 minutes: Team Status Meeting 📝 (Today from 1:00 PM to 1:30 PM)"),
                    ("msg-sm-2", "user-1", 2, "Today @Lisa will join our team huddle to provide updates on the launch. If you have questions, bring 'em. See you all soon!"),
                    ("msg-sm-3", "user-bot", 3, "A huddle happened: Lisa Dawson and 5 others were in the huddle for 28 minutes."),
                    ("msg-sm-4", "user-2", 4, "Please add any other notes from our sync today! (Canvas: 1/9 Meeting notes)"),
                ]
                for mid, auth_id, seq, body in seed_msgs:
                    msg = Message(
                        id=mid,
                        workspace_id="ws-default",
                        channel_id="ch-social-media",
                        author_id=auth_id,
                        sequence=seq,
                        body=body,
                        created_at=now,
                    )
                    session.add(msg)

                # Seed reactions on msg-sm-2
                session.add(Reaction(id="rx-1", workspace_id="ws-default", channel_id="ch-social-media", message_id="msg-sm-2", user_id="user-2", emoji="👍", created_at=now))
                session.add(Reaction(id="rx-2", workspace_id="ws-default", channel_id="ch-social-media", message_id="msg-sm-2", user_id="user-3", emoji="❤️", created_at=now))

                await session.commit()
        except Exception:
            await session.rollback()


async def create_db_and_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_defaults()

