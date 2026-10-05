from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.devices.models import DeviceSession, UserDevice


async def register_device(
    session: AsyncSession,
    *,
    user_id: str,
    device_identifier: str,
    platform: str,
    browser: str | None,
    session_token: str | None = None,
) -> UserDevice:
    device = None
    if hasattr(session, "saved"):
        for existing in getattr(session, "saved", []):
            if isinstance(existing, UserDevice) and existing.user_id == user_id and existing.device_identifier == device_identifier:
                device = existing
                break

    if device is None and hasattr(session, "execute"):
        result = await session.execute(
            select(UserDevice).where(
                UserDevice.user_id == user_id,
                UserDevice.device_identifier == device_identifier,
            )
        )
        device = result.scalars().first()

    if device is None:
        device = UserDevice(
            id=f"dev-{uuid4().hex[:18]}",
            user_id=user_id,
            device_identifier=device_identifier,
            platform=platform,
            browser=browser,
            session_token=session_token,
            last_seen_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        session.add(device)
        await session.flush() if hasattr(session, "flush") else None
    else:
        device.platform = platform
        device.browser = browser
        device.session_token = session_token or device.session_token
        device.last_seen_at = datetime.now(timezone.utc)

    if session_token:
        active_session = None
        if hasattr(session, "saved"):
            for existing in getattr(session, "saved", []):
                if isinstance(existing, DeviceSession) and existing.user_id == user_id and existing.session_token == session_token:
                    active_session = existing
                    break
        if active_session is None and hasattr(session, "execute"):
            result = await session.execute(
                select(DeviceSession).where(
                    DeviceSession.user_id == user_id,
                    DeviceSession.session_token == session_token,
                )
            )
            active_session = result.scalars().first()

        if active_session is None:
            active_session = DeviceSession(
                id=f"ds-{uuid4().hex[:18]}",
                user_id=user_id,
                device_id=device.id,
                session_token=session_token,
                created_at=datetime.now(timezone.utc),
            )
            session.add(active_session)
            await session.flush() if hasattr(session, "flush") else None

    if hasattr(session, "commit"):
        await session.commit()
    if hasattr(session, "refresh"):
        await session.refresh(device)
    return device


async def list_devices_for_user(session: AsyncSession, *, user_id: str) -> list[UserDevice]:
    if hasattr(session, "saved"):
        return [
            existing for existing in getattr(session, "saved", [])
            if isinstance(existing, UserDevice) and existing.user_id == user_id
        ]
    if hasattr(session, "execute"):
        result = await session.execute(select(UserDevice).where(UserDevice.user_id == user_id))
        return list(result.scalars().all())
    return []


async def revoke_device(session: AsyncSession, *, device_id: str, user_id: str) -> bool:
    if hasattr(session, "saved"):
        for existing in getattr(session, "saved", []):
            if isinstance(existing, UserDevice) and existing.id == device_id and existing.user_id == user_id:
                existing.revoked_at = datetime.now(timezone.utc)
                return True
        return False

    if hasattr(session, "execute"):
        result = await session.execute(
            select(UserDevice).where(
                UserDevice.id == device_id,
                UserDevice.user_id == user_id,
            )
        )
        device = result.scalars().first()
        if device is None:
            return False
        device.revoked_at = datetime.now(timezone.utc)
        if hasattr(session, "commit"):
            await session.commit()
        return True

    return False
