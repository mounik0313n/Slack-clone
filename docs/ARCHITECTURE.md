# Architecture

This platform follows a modular monolith with event-driven workers and derived search/indexing systems. PostgreSQL is the source of truth; Redis provides volatile state; NATS JetStream is the durable event backbone; OpenSearch is derived search; MinIO/S3 stores binary objects.

## Request flow

1. Client connects through the web app or REST API.
2. Authenticated requests resolve organization, workspace, and user context.
3. The API validates permissions server-side and writes transactional state.
4. The same transaction emits outbox events for asynchronous workers.
5. Realtime, notifications, search, workflows, and AI workers react asynchronously.

## System boundaries

- API: user-facing request handling and authorization
- Realtime Gateway: WebSocket delivery, presence, typing, replay
- Workers: NATS consumers, search indexing, notifications, AI, files
- Data services: Postgres, Redis, MinIO
- Derived services: OpenSearch and analytics projections

## Security model

All tenant resolution and resource authorization are enforced on the server. Client-supplied tenant or role identifiers are ignored.
