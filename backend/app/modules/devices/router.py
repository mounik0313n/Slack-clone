from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.modules.devices.service import list_devices_for_user, register_device, revoke_device

router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceRegisterRequest(BaseModel):
    user_id: str
    device_identifier: str
    platform: str = "web"
    browser: str | None = None
    session_token: str | None = None


class DeviceRevokeRequest(BaseModel):
    user_id: str


@router.post("/register")
async def register_device_endpoint(payload: DeviceRegisterRequest, session: AsyncSession = Depends(get_db)) -> dict:
    device = await register_device(
        session,
        user_id=payload.user_id,
        device_identifier=payload.device_identifier,
        platform=payload.platform,
        browser=payload.browser,
        session_token=payload.session_token,
    )
    return {
        "id": device.id,
        "user_id": device.user_id,
        "device_identifier": device.device_identifier,
        "platform": device.platform,
        "browser": device.browser,
        "revoked_at": device.revoked_at.isoformat() if device.revoked_at else None,
        "last_seen_at": device.last_seen_at.isoformat(),
    }


@router.get("")
async def list_devices_endpoint(user_id: str, session: AsyncSession = Depends(get_db)) -> list[dict]:
    devices = await list_devices_for_user(session, user_id=user_id)
    return [
        {
            "id": device.id,
            "user_id": device.user_id,
            "device_identifier": device.device_identifier,
            "platform": device.platform,
            "browser": device.browser,
            "revoked_at": device.revoked_at.isoformat() if device.revoked_at else None,
            "last_seen_at": device.last_seen_at.isoformat(),
        }
        for device in devices
    ]


@router.post("/{device_id}/revoke")
async def revoke_device_endpoint(device_id: str, payload: DeviceRevokeRequest, session: AsyncSession = Depends(get_db)) -> dict:
    revoked = await revoke_device(session, device_id=device_id, user_id=payload.user_id)
    return {"device_id": device_id, "revoked": revoked}
