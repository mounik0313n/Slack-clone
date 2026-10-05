from __future__ import annotations

from typing import AsyncGenerator

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import decode_token, settings
from app.database import AsyncSessionLocal

security = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    token = credentials.credentials
    try:
        claims = decode_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    if claims.get("type") not in {"access", "refresh"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    roles = claims.get("roles") or []
    if isinstance(roles, str):
        roles = [roles]
    if claims.get("role"):
        roles.append(claims["role"])

    return {
        "user_id": str(claims.get("sub", "unknown-user")),
        "email": claims.get("email", "unknown@example.com"),
        "role": claims.get("role", "member"),
        "roles": list(dict.fromkeys(roles or [claims.get("role", "member")])),
        "permissions": claims.get("permissions", []),
        "organization_id": claims.get("organization_id"),
        "workspace_id": claims.get("workspace_id"),
    }
