from __future__ import annotations

import pytest

from app.modules.reactions.service import add_reaction, remove_reaction
from app.modules.threads.service import create_thread, get_thread_by_root_message


@pytest.mark.asyncio
async def test_create_thread_from_root_message() -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.saved = []

        def add(self, obj):
            self.saved.append(obj)

        async def commit(self):
            return None

        async def refresh(self, obj):
            return None

    session = FakeSession()
    thread = await create_thread(
        session,
        workspace_id="ws-1",
        channel_id="ch-1",
        root_message_id="msg-1",
        author_id="user-1",
    )

    assert thread.root_message_id == "msg-1"
    assert thread.author_id == "user-1"
    assert len(session.saved) == 1


@pytest.mark.asyncio
async def test_get_thread_by_root_message() -> None:
    class FakeSession:
        def __init__(self) -> None:
            self._threads = {
                "msg-9": SimpleThread("msg-9", "ws-1", "ch-1", "user-1")
            }

        async def execute(self, query):
            return SimpleResult(self._threads)

    class SimpleResult:
        def __init__(self, threads):
            self._threads = threads

        def scalars(self):
            return SimpleScalars(self._threads)

    class SimpleScalars:
        def __init__(self, threads):
            self._threads = threads

        def first(self):
            return next(iter(self._threads.values()), None)

    class SimpleThread:
        def __init__(self, root_message_id, workspace_id, channel_id, author_id):
            self.root_message_id = root_message_id
            self.workspace_id = workspace_id
            self.channel_id = channel_id
            self.author_id = author_id

    thread = await get_thread_by_root_message(
        FakeSession(),
        workspace_id="ws-1",
        channel_id="ch-1",
        root_message_id="msg-9",
    )

    assert thread is not None
    assert thread.root_message_id == "msg-9"


@pytest.mark.asyncio
async def test_add_and_remove_reaction() -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.saved = []
            self.deleted = []

        def add(self, obj):
            self.saved.append(obj)

        async def commit(self):
            return None

        async def refresh(self, obj):
            return None

        def delete(self, obj):
            self.deleted.append(obj)

    session = FakeSession()
    reaction = await add_reaction(
        session,
        workspace_id="ws-1",
        channel_id="ch-1",
        message_id="msg-1",
        user_id="user-1",
        emoji="thumbsup",
    )

    assert reaction.emoji == "thumbsup"
    assert reaction.user_id == "user-1"

    removed = await remove_reaction(
        session,
        workspace_id="ws-1",
        channel_id="ch-1",
        message_id="msg-1",
        user_id="user-1",
        emoji="thumbsup",
    )

    assert removed is True
