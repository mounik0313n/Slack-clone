# Events and outbox

The application uses a transactional outbox pattern: a domain mutation and its outbox record are committed in the same PostgreSQL transaction. The outbox worker publishes durable events to NATS JetStream.

## Event envelope

```json
{
  "event_id": "uuid",
  "event_type": "message.created",
  "event_version": 1,
  "organization_id": "org-123",
  "workspace_id": "ws-123",
  "conversation_id": "ch-123",
  "actor_id": "user-123",
  "sequence": 42,
  "timestamp": "2026-01-01T00:00:00Z",
  "payload": {}
}
```

Consumers are idempotent and safe to retry. Event producers do not block user-facing success on downstream derived systems.
