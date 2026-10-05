# Operations

Operations runbooks cover metrics, logs, health checks, and dependency health.

## Health endpoints

- `/health`
- `/health/live`
- `/health/ready`
- `/metrics`

## Observability

OpenTelemetry, Prometheus, and Grafana provide traces and metrics across frontend, API, DB, NATS, workers, and OpenSearch. Structured JSON logging is used for request and event correlation.

## Service hygiene

- graceful shutdown
- retry and backoff for transient failures
- dead-letter handling for worker errors
- circuit-breaker behavior around third-party providers
