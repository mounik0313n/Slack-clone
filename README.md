# Slack-clone

A production-oriented Slack-class collaboration platform built with a FastAPI backend, React + Vite frontend, PostgreSQL, Redis, NATS, and Docker deployment tooling.

## Quick start

```bash
docker compose up -d
```

Then open the frontend at http://localhost:5173 and the API at http://localhost:8000/docs.

## Repository layout

- `backend/` – FastAPI application, domain modules, database migrations, and workers
- `frontend/` – React + TypeScript + Vite UI with offline sync and reconnect handling
- `infrastructure/` – Docker, Kubernetes, Terraform, Helm, and deployment assets
- `docs/` – architecture, security, deployment, compliance, and API documentation
- `tests/` – backend and frontend validation suites

## Stack summary

- Backend: Python 3.13, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2
- Frontend: React 19, TypeScript, Vite, TanStack Query, Zustand
- Data: PostgreSQL, Redis, NATS JetStream, OpenSearch, MinIO
- Deployment: Docker Compose, Kubernetes, Helm, Terraform, GitHub Actions

## Source of truth

- PostgreSQL = authoritative state
- NATS = event transport
- Redis = ephemeral hot state
- OpenSearch = derived search state
- MinIO/S3 = object storage
- WebSocket = delivery mechanism
- WebRTC = media transport

## Offline resilience

- IndexedDB-backed local persistence for drafts and pending mutations
- reconnect-driven authoritative sync using the existing server sync protocol
- heartbeat-based stale connection pruning and runtime recoverability

## Development

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

See the detailed docs for environment variables and deployment guidance.
