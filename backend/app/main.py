from __future__ import annotations

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import AsyncSessionLocal, create_db_and_tables
from app.modules.auth.router import router as auth_router
from app.modules.organizations.router import router as organizations_router
from app.modules.workspaces.router import router as workspaces_router
from app.modules.channels.router import router as channels_router
from app.modules.conversations.router import router as conversations_router
from app.modules.devices.router import router as devices_router
from app.modules.mentions.router import router as mentions_router
from app.modules.messages.router import router as messages_router
from app.modules.notifications.router import router as notifications_router
from app.modules.presence.service import PresenceService
from app.modules.read_states.router import router as read_states_router
from app.modules.reactions.router import router as reactions_router
from app.modules.sync.service import collect_sync_snapshot
from app.modules.sync.router import router as sync_router
from app.modules.threads.router import router as threads_router
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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready")
async def health_ready() -> dict[str, str]:
    return {"status": "ready"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    client_id = websocket.query_params.get("client_id", "anonymous")
    await realtime_gateway.connect(websocket, client_id)
    await websocket.send_json({"event_type": "connected", "payload": {"status": "ok", "client_id": client_id}})
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
                for channel in channels:
                    realtime_gateway.subscribe(client_id, str(channel))
                await websocket.send_json({"event_type": "subscribed", "payload": {"channels": channels}})
                replay_events = await realtime_gateway.resume(client_id, [str(channel) for channel in channels])
                await websocket.send_json({"event_type": "resume", "payload": {"channels": channels, "events": replay_events}})
                continue

            if event_type == "unsubscribe":
                channels = payload.get("channels", [])
                for channel in channels:
                    realtime_gateway.unsubscribe(client_id, str(channel))
                await websocket.send_json({"event_type": "unsubscribed", "payload": {"channels": channels}})
                continue

            if event_type in {"resume", "replay"}:
                channels = payload.get("channels", []) or payload.get("payload", {}).get("channels", [])
                replay_events = await realtime_gateway.resume(client_id, [str(channel) for channel in channels])
                if not replay_events:
                    await websocket.send_json({
                        "event_type": "sync.required",
                        "type": "sync.required",
                        "payload": {
                            "reason": "EVENT_HISTORY_UNAVAILABLE",
                            "workspace_id": payload.get("workspace_id") or payload.get("payload", {}).get("workspace_id"),
                            "channels": channels,
                        },
                    })
                else:
                    await websocket.send_json({"event_type": "resume", "payload": {"channels": channels, "events": replay_events}})
                continue

            if event_type == "sync.request" or payload.get("type") == "sync.request":
                user_id = payload.get("user_id") or client_id
                workspace_id = payload.get("workspace_id") or payload.get("payload", {}).get("workspace_id") or "ws-default"
                cursor = payload.get("cursor") or payload.get("payload", {}).get("cursor")
                conversation_ids = payload.get("conversations") or payload.get("payload", {}).get("conversations") or []
                async with AsyncSessionLocal() as db_session:
                    snapshot = await collect_sync_snapshot(
                        db_session,
                        user_id=user_id,
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
                status = str(payload.get("payload", {}).get("status", "online")).lower()
                presence_service.set_presence(client_id, status)
                await realtime_gateway.broadcast("presence.changed", {"client_id": client_id, "status": status})
                continue

            if event_type in {"typing.start", "typing.stop"}:
                event_name = "typing.started" if event_type == "typing.start" else "typing.stopped"
                await realtime_gateway.broadcast(event_name, {"client_id": client_id, **payload.get("payload", {})})
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
