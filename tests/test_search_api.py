from __future__ import annotations

from datetime import datetime, timezone
import pytest

from app.modules.messages.models import Message
from app.modules.search.router import search_messages_endpoint


class MockSearchSession:
    def __init__(self, messages: list[Message]) -> None:
        self.messages = messages

    async def execute(self, statement):
        class MockResult:
            def __init__(self, data):
                self._data = data

            def scalars(self):
                class MockScalars:
                    def __init__(self, data):
                        self._data = data

                    def all(self):
                        return self._data

                return MockScalars(self._data)

        return MockResult(self.messages)


@pytest.mark.asyncio
async def test_search_messages_returns_matching_results_and_snippets() -> None:
    msg1 = Message(
        id="msg-1",
        workspace_id="ws-default",
        channel_id="ch-general",
        author_id="user-1",
        sequence=1,
        body="Welcome to the company slack project! Let's deploy the services.",
        created_at=datetime.now(timezone.utc),
    )
    session = MockSearchSession([msg1])

    response = await search_messages_endpoint(
        query="deploy",
        workspace_id="ws-default",
        channel_id=None,
        limit=10,
        session=session,
        current_user={"user_id": "user-1", "workspace_id": "ws-default", "role": "admin", "permissions": ["message.read"]},
    )

    assert response.query == "deploy"
    assert response.total == 1
    assert len(response.results) == 1
    assert response.results[0].id == "msg-1"
    assert "deploy" in response.results[0].snippet.lower()
