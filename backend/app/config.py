from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, List

import jwt
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "slack-platform"
    app_env: str = "development"
    debug: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"])
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/slack_platform"
    redis_url: str = "redis://localhost:6379/0"
    nats_url: str = "nats://localhost:4222"
    secret_key: str = "change-this-in-production-to-a-long-random-key-123456"
    jwt_secret_key: str = "change-this-jwt-secret-to-a-long-random-key-1234567890"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.app_env.lower() == "production":
            placeholder_values = {
                "change-this-in-production-to-a-long-random-key-123456",
                "change-this-jwt-secret-to-a-long-random-key-1234567890",
                "postgres",
                "redis_password",
                "minioadmin",
                "admin",
            }
            if self.secret_key in placeholder_values:
                raise ValueError("SECRET_KEY must be set to a real secret in production")
            if self.jwt_secret_key in placeholder_values:
                raise ValueError("JWT_SECRET_KEY must be set to a real secret in production")
            if not self.cors_origins:
                raise ValueError("CORS_ORIGINS must include the production frontend URL")
        return self

    @property
    def token_context(self) -> dict[str, Any]:
        return {"iss": self.app_name, "aud": "slack-platform"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def create_token(subject: str, *, token_type: str, expires_minutes: int | None = None, **extra_claims: Any) -> str:
    now = datetime.now(timezone.utc)
    expires_delta = timedelta(minutes=expires_minutes or settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        **settings.token_context,
        **extra_claims,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm], audience="slack-platform")
