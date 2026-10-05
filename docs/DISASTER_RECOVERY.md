# Disaster recovery

The system is designed for rebuildability from authoritative state.

## Recovery principles

- PostgreSQL is the system of record
- derived stores such as OpenSearch are rebuildable from events
- object storage is recoverable via bucket snapshots or replication
- NATS JetStream and the transactional outbox provide replay capability

## Recommended procedures

1. Back up PostgreSQL and object storage
2. Validate the restore path for the database and object store
3. Rebuild derived search indexes from replayed events
4. Restore the event backbone and workers
5. Validate health, readiness, and user-authenticated flows
