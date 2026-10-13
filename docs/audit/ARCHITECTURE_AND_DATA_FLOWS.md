# Architecture & Data Flows

## 1. System Overview
The platform is designed as an end-to-end, multi-tenant collaboration engine structured around three core planes:
1. **Application & Client Plane:** React 19 / TypeScript SPA with offline mutation queues and WebSocket subscriptions.
2. **Control & Ingestion Plane:** FastAPI asynchronous application server enforcing authentication, authorization, rate-limiting, and sequence allocation.
3. **Storage & Persistence Plane:** Neon Lakebase PostgreSQL, Alembic migrations, and Realtime WebSocket event gateway.

---

## 2. End-to-End Message Data Flow

```mermaid
sequenceDiagram
    autonumber
    actor User as Client (Web/Mobile)
    participant UI as React SPA (App.tsx)
    participant Queue as Offline Mutation Queue
    participant API as FastAPI Backend
    participant Auth as Auth & Tenancy Guard
    participant DB as Neon PostgreSQL
    participant RT as RealtimeGateway
    actor Peer as Subscribed Peer Client

    User->>UI: Types message & clicks Send
    UI->>UI: Optimistic Render (Status: PENDING)
    UI->>Queue: Enqueue mutation (client_message_id)
    Queue->>API: POST /api/v1/messages (Bearer JWT)
    API->>Auth: Validate JWT & check tenant workspace bounds
    Auth-->>API: Validated (author_id = sub)
    API->>DB: Atomic sequence increment & INSERT message
    DB-->>API: Message persisted (id: msg-..., seq: 142)
    API->>RT: broadcast("message.created", channel="ch-general")
    par Server Response to Sender
        API-->>Queue: HTTP 201 Created (MessageRead)
        Queue->>UI: Reconcile optimistic ID with canonical server ID
    and Real-Time Broadcast to Peers
        RT-->>Peer: WebSocket frame {"event_type": "message.created", ...}
        Peer->>Peer: Append message to conversation view & mark read
    end
```

---

## 3. Real-Time Reconnection & Offline Sync Flow

```mermaid
stateDiagram-v2
    [*] --> Connected: Page Load
    Connected --> Disconnected: Network Drop / Sleep
    Disconnected --> Buffering: Outgoing Messages
    Buffering --> Buffering: Save to IndexedDB
    Disconnected --> Reconnecting: Exponential Backoff (1s, 2s, 4s, 8s)
    Reconnecting --> Connected: WebSocket Reconnected
    Connected --> Resuming: Send "resume" frame with channel list
    Resuming --> Flushing: Replay buffered events
    Flushing --> Idle: Flush pending mutations to POST /messages
    Idle --> Connected
```

---

## 4. Multi-Tenant Authorization Model
The system uses strict contextual tenancy isolation:
1. Every authenticated token contains:
   - `sub`: User ID
   - `role`: Role (`admin`, `member`, `guest`)
   - `permissions`: Scoped rights (`workspace.read`, `channel.create`, `message.create`, `audit.read`, etc.)
2. `ensure_tenant_boundaries(claims, workspace_id, organization_id)` ensures that clients cannot craft requests targeting workspaces or organizations outside their authorization boundary.
3. Any cross-tenant attempt immediately raises a `PermissionError` (HTTP 403 Forbidden).
