# Repository Inventory & Baseline Audit

## 1. Overview
- **Repository:** `mounik0313n/Slack-clone`
- **Audit Date:** 2026-10-13
- **Primary Architecture:** Multi-tenant distributed collaboration platform (Slack-class)
- **Frontend Stack:** React 19, TypeScript 5.7, Vite 6, Zustand 5, TanStack React Query 5, Vanilla CSS Design System with Slack Light Aubergine Theme.
- **Backend Stack:** Python 3.13 / FastAPI, SQLAlchemy 2 (asyncpg), Pydantic v2, Argon2-cffi, PyJWT.
- **Database Engine:** PostgreSQL 16 (Hosted on Neon Lakebase with SSL SNI and Connection Pooling).
- **Real-Time Gateway:** Async WebSocket Gateway with client-side buffer queue and server event broadcast.
- **Hosting / Deployments:** 
  - Frontend: Vercel (`https://slack-clone-xi-rust.vercel.app`)
  - Backend: Render (`https://slack-platform-api.onrender.com`)
  - Database: Neon Postgres (`ep-withered-voice-b3h40y3k.c-4.ap-southeast-1.aws.neon.tech`)

---

## 2. Inventory by Component

### 2.1 Backend Modules (`backend/app/modules/`)
| Module | Components | Endpoints Registered | Status |
|---|---|---|---|
| `auth` | User model, Argon2 hasher, JWT issue/refresh, token revocation | `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/me`, `/auth/logout`, `/auth/password-reset/*` | VERIFIED |
| `organizations` | Organization model, multi-tenant container | `/organizations`, `/organizations/{org_id}` | VERIFIED |
| `workspaces` | Workspace model, membership association | `/workspaces`, `/workspaces/{ws_id}` | VERIFIED |
| `channels` | Channel model, topic/purpose, public/private | `/channels`, `/channels/{channel_id}` | VERIFIED |
| `conversations` | DMs, Group DMs, multi-party memberships | `/conversations`, `/conversations/{conv_id}` | VERIFIED |
| `messages` | Message model, cursor pagination, thread_id | `/messages`, `/messages/{msg_id}` | VERIFIED |
| `threads` | Thread replies, count aggregation | `/threads/{thread_id}/replies` | VERIFIED |
| `reactions` | Emoji reactions, add/remove, live broadcast | `/reactions`, `/reactions/{msg_id}/{user_id}/{emoji}` | VERIFIED |
| `mentions` | User & channel mentions, trigger notifications | `/mentions` | VERIFIED |
| `read_states` | Channel unread tracking, last-read timestamp | `/read-states` | VERIFIED |
| `notifications` | In-app alerts, unread counts | `/notifications` | VERIFIED |
| `devices` | Device registration, push session mapping | `/devices` | VERIFIED |
| `sync` | Offline snapshot collection, delta hydration | `/sync/snapshot` | VERIFIED |
| `search` | Full-text query, snippet generation, channel filter | `/search/messages` | VERIFIED |
| `files` | Attachment metadata, upload size validation (50MB) | `/files/upload`, `/files/{file_id}` | VERIFIED |
| `admin` | Member management, RBAC, audit logging, stats | `/admin/members`, `/admin/members/{id}/role`, `/admin/audit-logs`, `/admin/stats` | VERIFIED |
| `ai` | Channel summaries, Slackbot assistant | `/ai/summarize`, `/ai/query` | VERIFIED |

### 2.2 Real-time Subsystem (`backend/app/realtime/`)
- `RealtimeGateway`: Manages active WebSocket client sessions, channel subscriptions, and non-blocking event broadcasting (`message.created`, `reaction.created`, `presence.changed`, `typing.started`).
- Authentication: Authenticates via JWT query parameter or subsequent `authenticate` frame; rejects revoked tokens.
- Replay: Replays in-memory buffered events on client reconnect.

### 2.3 Frontend Application (`frontend/src/`)
- `App.tsx`: Full Slack collaboration interface featuring:
  - Global top navigation bar with search trigger and presence badge
  - Collapsible Slack Aubergine sidebar (`#3F0E40`) with workspace switcher
  - Channels directory, DMs, Threads, Huddles, Canvas, Drafts, and Admin views
  - Rich chat feed with optimistic message dispatch, emoji picker, threads, edit/delete
  - Integrated Search modal, Member Directory modal, Huddle overlay modal, AI assistant drawer
- `offline/`: IndexedDB persistence (`indexedDb.ts`), background mutation queue (`mutationQueue.ts`), connectivity monitor (`connectivity.ts`), and sync coordinator (`syncManager.ts`).
- `realtime/`: Realtime WebSocket client (`realtimeClient.ts`) with reconnect backoff and offline send buffering.

### 2.4 Database & Migrations
- `database.py`: SQLAlchemy async engine with asyncpg dialect, NullPool connection handling, and SSL auto-detection for Neon.
- `migrations/`: Alembic migrations baseline initialized (`alembic.ini`, `env.py`, `script.py.mako`, `versions/0001_initial_schema.py`).
