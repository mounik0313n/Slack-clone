# Database

The authoritative application state lives in PostgreSQL.

## Source of truth rules

- PostgreSQL stores users, organizations, workspaces, channels, messages, permissions, workflow definitions, audits, and object metadata.
- Redis stores ephemeral presence and connection metadata.
- NATS stores event transport and durable streams.
- OpenSearch stores derived search indexes.

## Migration model

All schema changes must be managed with Alembic. The repository provides an Alembic configuration and a migration-friendly module layout.

## Key design principles

- UUID or ULID-style identifiers are preferred.
- Soft-delete and retention policies are enforced at the application layer.
- Every domain mutation that emits an event should create an outbox row in the same transaction.
