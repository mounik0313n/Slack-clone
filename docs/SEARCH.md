# Search

OpenSearch hosts derived, authorization-aware documents for messages, files, users, and channels. Search is not authoritative and can be rebuilt from PostgreSQL state.

## Indexing model

- PostgreSQL persists authoritative records
- Outbox emits domain events
- Search worker transforms and persists derived documents
- Accessible results are filtered by authenticated resource permission before returning data

## Query semantics

The platform supports basic filters such as `from:`, `in:`, `after:`, `before:`, `has:file`, and `has:link` for multi-tenant user search journeys.
