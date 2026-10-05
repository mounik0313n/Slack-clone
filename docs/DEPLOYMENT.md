# Deployment

The repository includes a Docker Compose setup for the full platform stack and a Kubernetes/Helm/Terraform foundation.

## Local deployment

```bash
docker compose up -d
```

This starts PostgreSQL, Redis, NATS, OpenSearch, MinIO, and the API/frontend services.

## Production guidance

- use separate secrets management
- keep TLS termination at the ingress layer
- load-balance API and realtime separately when scaling horizontally
- run database and backups according to disaster-recovery playbooks
