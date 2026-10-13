# Remediation Log & Change Record

## Entry 1: SEC-001 (Critical IDOR on Message Author Resolution)
- **Target File:** `backend/app/modules/messages/router.py`
- **Change:** Substituted client-supplied `payload.author_id` with `current_user["user_id"]` derived strictly from the authenticated token claims.
- **Rationale:** Prevented impersonation and unauthorized message author forging.
- **Evidence:** `tests/test_realtime_flow.py`, `tests/test_message_idempotency.py` passing.

---

## Entry 2: SEC-002 (Refresh Token Rotation & Replay Protection)
- **Target Files:** `backend/app/modules/auth/service.py`, `backend/app/config.py`
- **Change:**
  1. Added unique `jti` nonces using `secrets.token_hex(16)` to all tokens created by `create_token()`.
  2. Implemented single-use refresh token rotation in `refresh_user_tokens()`.
  3. Added `_revoked_tokens` in-memory tracking and revocation verification.
- **Rationale:** Eliminated refresh token replay vulnerabilities.
- **Evidence:** `tests/test_auth_security.py::test_refresh_token_rotation_and_replay_prevention` passing.

---

## Entry 3: SEC-003 (WebSocket JWT Authentication & Revocation Verification)
- **Target File:** `backend/app/main.py`
- **Change:** Enhanced `/ws` endpoint to decode JWT tokens via query parameter or incoming `authenticate` frame. Validated that token is not in `_revoked_tokens`.
- **Rationale:** Prevented unauthenticated actors from connecting with arbitrary client IDs.
- **Evidence:** `tests/test_websocket_realtime_auth.py` passing.

---

## Entry 4: Missing Collaboration & Management Routers
- **Target Files:**
  - `backend/app/modules/search/`: `schemas.py`, `router.py`
  - `backend/app/modules/files/`: `models.py`, `schemas.py`, `router.py`
  - `backend/app/modules/admin/`: `schemas.py`, `router.py`
  - `backend/app/modules/ai/`: `schemas.py`, `router.py`
  - `backend/app/main.py`: Mounted all new routers under `/api/v1`
- **Change:** Implemented full backend endpoints for search with match snippets, file uploads with 50MB ceiling, admin member roles and audit logs, and AI channel summarization.
- **Rationale:** Closed the gap between documented capabilities and runtime implementation.
- **Evidence:** `tests/test_search_api.py`, `tests/test_files_api.py`, `tests/test_admin_api.py` passing.

---

## Entry 5: Alembic Migrations Infrastructure
- **Target Files:**
  - `backend/migrations/env.py`
  - `backend/migrations/script.py.mako`
  - `backend/migrations/versions/0001_initial_schema.py`
- **Change:** Created versioned Alembic schema migrations setup with asyncpg engine support.
- **Rationale:** Complies with Phase 2 requirement to maintain versioned migrations rather than relying solely on runtime startup DDL.
- **Evidence:** Alembic configuration successfully initialized.

---

## Entry 6: Frontend Realtime Client Cleanup & Testing
- **Target Files:**
  - `frontend/src/realtime/realtimeClient.ts`
  - `frontend/src/realtime/realtimeClient.test.ts`
  - `frontend/src/offline/connectivity.test.ts`
- **Change:** Added return cleanup function to `realtimeClient.on(...)` to prevent listener leaks; added `onStatus` alias; added Vitest unit tests.
- **Rationale:** Prevents memory leaks in React lifecycle hooks and verifies real-time behavior.
- **Evidence:** Vitest passing 3/3 tests; Vite production build passing in 1.72s.
