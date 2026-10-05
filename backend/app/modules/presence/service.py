from __future__ import annotations

from typing import Any

from app.config import settings

try:
    import redis
except Exception:  # pragma: no cover - optional dependency fallback
    redis = None


class PresenceService:
    def __init__(self, redis_client: Any | None = None) -> None:
        self.redis_client = redis_client
        self._local_store: dict[str, str] = {}
        if self.redis_client is None and redis is not None:
            try:
                self.redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
                self.redis_client.ping()
            except Exception:
                self.redis_client = None

    def set_presence(self, user_id: str, status: str) -> str:
        normalized = status.lower()
        if normalized == "offline":
            if self.redis_client is not None:
                self.redis_client.delete(f"presence:{user_id}")
            self._local_store.pop(user_id, None)
            return normalized
        if self.redis_client is not None:
            self.redis_client.setex(f"presence:{user_id}", 30, normalized)
        self._local_store[user_id] = normalized
        return normalized

    def get_presence(self, user_id: str) -> str | None:
        if self.redis_client is not None:
            value = self.redis_client.get(f"presence:{user_id}")
            if value:
                return value
        return self._local_store.get(user_id)

    def get_online_users(self) -> set[str]:
        if self.redis_client is not None:
            keys = self.redis_client.keys("presence:*")
            return {key.decode("utf-8").split(":", 1)[1] for key in keys}
        return set(self._local_store.keys())
