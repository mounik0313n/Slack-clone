# Operational Runbook & SRE Guide

## 1. Local Development Quickstart

### Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL (or Neon cloud connection string)

### Starting the Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Starting the Frontend
```bash
cd frontend
npm install
npm run dev
```

---

## 2. Automated Test Execution

### Running Backend Tests
```bash
# In repository root
$env:PYTHONPATH="backend"
pytest -q tests
```

### Running Frontend Tests & Typecheck
```bash
cd frontend
npm run test     # Executes Vitest suite
npm run build    # Runs TypeScript typecheck & Vite production bundle
```

---

## 3. Database Migrations (Alembic)

### Apply Pending Migrations
```bash
cd backend
alembic upgrade head
```

### Create a New Migration
```bash
cd backend
alembic revision -m "add_new_feature_table"
```

---

## 4. Environment Variables Reference

| Variable | Scope | Purpose | Example |
|---|---|---|---|
| `DATABASE_URL` | Backend | PostgreSQL connection URI | `postgresql+asyncpg://user:pass@host/slack_platform` |
| `SECRET_KEY` | Backend | Application encryption key | 32+ character random secret |
| `JWT_SECRET_KEY` | Backend | Signing key for access & refresh tokens | 32+ character random secret |
| `CORS_ORIGINS` | Backend | Permitted web client origins | `["https://slack-clone-xi-rust.vercel.app"]` |
| `VITE_API_URL` | Frontend | Target API URL | `https://slack-platform-api.onrender.com` |
| `VITE_WS_URL` | Frontend | Target WebSocket gateway URL | `wss://slack-platform-api.onrender.com/ws` |

---

## 5. Incident Response & Health Checks

### Liveness & Readiness Probes
- **Service Root:** `GET /`
- **Core Health:** `GET /health`
- **Liveness:** `GET /health/live`
- **Readiness:** `GET /health/ready`

### Procedure: API Unavailable (HTTP 502 / 503)
1. Check Render service dashboard: verify container logs for memory pressure or unhandled exceptions.
2. Verify Neon database compute state: ensure Neon project branch compute has not been suspended.
3. Validate connection string SSL parameters (`DATABASE_USE_SSL=true`).

### Procedure: WebSocket Reconnect Loop
1. Check browser dev console for CORS or SSL handshake errors.
2. Ensure Vercel frontend has correct `VITE_WS_URL` configured in environment variables.
3. Test WebSocket connection directly via `wscat -c wss://slack-platform-api.onrender.com/ws`.
