from __future__ import annotations

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import decode_token, settings
from app.database import AsyncSessionLocal, create_db_and_tables
from app.modules.admin.router import router as admin_router
from app.modules.ai.router import router as ai_router
from app.modules.auth.router import router as auth_router
from app.modules.auth.service import is_token_revoked
from app.modules.channels.models import Channel, ChannelMember
from app.modules.channels.router import router as channels_router
from app.modules.conversations.models import Conversation, ConversationMember
from app.modules.conversations.router import router as conversations_router
from app.modules.devices.router import router as devices_router
from app.modules.files.router import router as files_router
from app.modules.mentions.router import router as mentions_router
from app.modules.messages.router import router as messages_router
from app.modules.notifications.router import router as notifications_router
from app.modules.organizations.router import router as organizations_router
from app.modules.presence.service import PresenceService
from app.modules.read_states.router import router as read_states_router
from app.modules.reactions.router import router as reactions_router
from app.modules.search.router import router as search_router
from app.modules.sync.router import router as sync_router
from app.modules.sync.service import collect_sync_snapshot
from app.modules.threads.router import router as threads_router
from app.modules.workspaces.router import router as workspaces_router
from app.realtime.gateway import RealtimeGateway


@asynccontextmanager
async def lifespan(_: FastAPI):
    await create_db_and_tables()
    yield


app = FastAPI(
    title="Slack Platform API",
    version="0.1.0",
    description="Production-oriented Slack-class collaboration platform API",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

realtime_gateway = RealtimeGateway()
presence_service = PresenceService()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "service": "Slack Platform API",
        "docs_url": "/docs",
        "ready": True,
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready")
async def health_ready() -> dict[str, str]:
    return {"status": "ready"}


async def verify_subscription_access(
    session: AsyncSession,
    *,
    user_id: str,
    workspace_id: str,
    target_id: str,
    user_role: str,
) -> bool:
    # 1. Direct personal notifications topic
    if target_id == user_id or target_id == f"user:{user_id}":
        return True

    # 2. Channel lookup & membership check
    channel = await session.get(Channel, target_id)
    if channel:
        if channel.workspace_id != workspace_id:
            return False
        if not channel.is_private:
            return True
        cm = await session.scalar(
            select(ChannelMember).where(
                ChannelMember.channel_id == target_id,
                ChannelMember.user_id == user_id,
            )
        )
        return cm is not None or user_role == "admin"

    # 3. Conversation lookup (DMs / Group DMs)
    conv = await session.get(Conversation, target_id)
    if conv:
        if conv.workspace_id != workspace_id:
            return False
        mem = await session.scalar(
            select(ConversationMember).where(
                ConversationMember.conversation_id == target_id,
                ConversationMember.user_id == user_id,
            )
        )
        return mem is not None

    return False


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    # 1. Require verified authentication BEFORE accepting WebSocket connections
    token = websocket.query_params.get("token")
    if not token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif websocket.headers.get("sec-websocket-protocol"):
            token = websocket.headers.get("sec-websocket-protocol").strip()

    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication token required")
        return

    if is_token_revoked(token):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token has been revoked")
        return

    try:
        claims = decode_token(token)
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired token")
        return

    if not claims or claims.get("type") != "access":
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Access token required")
        return

    client_id = str(claims.get("sub", ""))
    if not client_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Subject claim missing")
        return

    workspace_id = str(claims.get("workspace_id") or "ws-default")
    role = str(claims.get("role") or "member")

    await realtime_gateway.connect(websocket, client_id)
    await websocket.send_json({
        "event_type": "connected",
        "payload": {
            "status": "ok",
            "client_id": client_id,
            "workspace_id": workspace_id,
            "role": role,
        },
    })
    try:
        while True:
            raw_message = await websocket.receive_text()
            try:
                payload = json.loads(raw_message)
            except json.JSONDecodeError:
                payload = {"event_type": "echo", "payload": {"message": raw_message}}

            event_type = payload.get("event_type")

            if event_type == "subscribe":
                channels = payload.get("channels", [])
                authorized_channels: list[str] = []
                async with AsyncSessionLocal() as db_session:
                    for ch in channels:
                        ch_str = str(ch)
                        is_auth = await verify_subscription_access(
                            db_session,
                            user_id=client_id,
                            workspace_id=workspace_id,
                            target_id=ch_str,
                            user_role=role,
                        )
                        if is_auth:
                            realtime_gateway.subscribe(client_id, ch_str)
                            authorized_channels.append(ch_str)
                        else:
                            await websocket.send_json({
                                "event_type": "subscription_error",
                                "payload": {
                                    "code": "FORBIDDEN",
                                    "channel": ch_str,
                                    "message": f"User {client_id} is not authorized to subscribe to {ch_str}",
                                },
                            })

                await websocket.send_json({"event_type": "subscribed", "payload": {"channels": authorized_channels}})
                replay_events = await realtime_gateway.resume(client_id, authorized_channels)
                await websocket.send_json({"event_type": "resume", "payload": {"channels": authorized_channels, "events": replay_events}})
                continue

            if event_type == "unsubscribe":
                channels = payload.get("channels", [])
                for channel in channels:
                    realtime_gateway.unsubscribe(client_id, str(channel))
                await websocket.send_json({"event_type": "unsubscribed", "payload": {"channels": channels}})
                continue

            if event_type in {"resume", "replay"}:
                channels = payload.get("channels", []) or payload.get("payload", {}).get("channels", [])
                authorized_channels = []
                async with AsyncSessionLocal() as db_session:
                    for ch in channels:
                        ch_str = str(ch)
                        if await verify_subscription_access(db_session, user_id=client_id, workspace_id=workspace_id, target_id=ch_str, user_role=role):
                            authorized_channels.append(ch_str)

                replay_events = await realtime_gateway.resume(client_id, authorized_channels)
                if not replay_events:
                    await websocket.send_json({
                        "event_type": "sync.required",
                        "type": "sync.required",
                        "payload": {
                            "reason": "EVENT_HISTORY_UNAVAILABLE",
                            "workspace_id": workspace_id,
                            "channels": authorized_channels,
                        },
                    })
                else:
                    await websocket.send_json({"event_type": "resume", "payload": {"channels": authorized_channels, "events": replay_events}})
                continue

            if event_type == "sync.request" or payload.get("type") == "sync.request":
                cursor = payload.get("cursor") or payload.get("payload", {}).get("cursor")
                conversation_ids = payload.get("conversations") or payload.get("payload", {}).get("conversations") or []
                async with AsyncSessionLocal() as db_session:
                    snapshot = await collect_sync_snapshot(
                        db_session,
                        user_id=client_id,
                        workspace_id=workspace_id,
                        conversation_ids=[str(conv) for conv in conversation_ids] if conversation_ids else None,
                        cursor=str(cursor) if cursor is not None else None,
                    )
                await websocket.send_json({"event_type": "sync.response", "type": "sync.response", "payload": snapshot})
                continue

            if event_type == "ping":
                await realtime_gateway.heartbeat(client_id, sync_required=bool(payload.get("sync_required")))
                await websocket.send_json({"event_type": "pong", "payload": {"client_id": client_id}})
                continue

            if event_type == "heartbeat":
                await realtime_gateway.heartbeat(client_id, sync_required=bool(payload.get("sync_required")))
                continue

            if event_type == "presence":
                status_val = str(payload.get("payload", {}).get("status", "online")).lower()
                presence_service.set_presence(client_id, status_val)
                await realtime_gateway.broadcast("presence.changed", {"client_id": client_id, "status": status_val})
                continue

            if event_type in {"typing.start", "typing.stop"}:
                event_name = "typing.started" if event_type == "typing.start" else "typing.stopped"
                target_channel = payload.get("payload", {}).get("channel_id")
                await realtime_gateway.broadcast(event_name, {"client_id": client_id, **payload.get("payload", {})}, channel=target_channel)
                continue

            await websocket.send_json({"event_type": "echo", "payload": {"message": payload}})
    except WebSocketDisconnect:
        realtime_gateway.disconnect(client_id)


app.include_router(auth_router, prefix="/api/v1")
app.include_router(organizations_router, prefix="/api/v1")
app.include_router(workspaces_router, prefix="/api/v1")
app.include_router(channels_router, prefix="/api/v1")
app.include_router(conversations_router, prefix="/api/v1")
app.include_router(mentions_router, prefix="/api/v1")
app.include_router(messages_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(read_states_router, prefix="/api/v1")
app.include_router(sync_router, prefix="/api/v1")
app.include_router(devices_router, prefix="/api/v1")
app.include_router(threads_router, prefix="/api/v1")
app.include_router(reactions_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(files_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
