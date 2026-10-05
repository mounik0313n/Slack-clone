# Security

The platform enforces tenant isolation, RBAC, token rotation, and secure defaults.

## Security controls

- HTTPS-only deployment with HSTS and strict CORS
- Password hashing with Argon2id
- short-lived JWT access tokens and rotated refresh tokens
- audit logging for sensitive admin actions
- rate limiting at the API and auth layers
- workspace and organization boundary enforcement in every repository query

## Operational principles

Secrets are injected via environment variables and never hardcoded. Production deployments must use TLS, secure secrets managers, and least-privilege service accounts.
