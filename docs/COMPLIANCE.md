# Compliance and retention

Compliance controls include audit logging, retention policies, legal hold architecture, and data export support.

## Policy model

- retention policies are scoped to organization and workspace contexts
- legal holds prevent deletion or purge until release
- export jobs are created asynchronously and respect RBAC
- audit records persist user, staff, and system actions with metadata and result codes

This architecture supports regulated environments without coupling business logic to a single storage vendor.
