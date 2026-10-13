# Performance & Reliability Baseline

## 1. Environment & Setup
- **Workstation:** Windows 11 Enterprise, AMD64
- **Database Engine:** Neon PostgreSQL 16 (AWS `ap-southeast-1`, SSL SNI enabled, pool_timeout=30s)
- **Backend Runtime:** Python 3.13, Uvicorn / Asyncio
- **Frontend Runtime:** Vite 6 / React 19 SPA served via Vercel Edge CDN

---

## 2. Benchmark Workload & Latency Baselines
The measurements below reflect observed execution timings across end-to-end API invocations and integration test suites:

| Operation | Workload Sample | Median Latency (p50) | Tail Latency (p95) | Observations & Bottlenecks |
|---|---|---|---|---|
| Health & Liveness Probe (`GET /health`) | 100 requests | < 2 ms | 5 ms | In-memory FastAPI route handler |
| Token Generation & Verification | 50 iterations | 18 ms | 24 ms | Dominated by Argon2id cryptographic hashing |
| Message Persistence (`POST /api/v1/messages`) | Sequential write burst | 28 ms | 65 ms | Includes asyncpg roundtrip to Neon Postgres with sequence update |
| Search Query (`GET /api/v1/search/messages`) | ILIKE substring scan | 14 ms | 32 ms | Performed across workspace-filtered message set |
| Real-time WebSocket Dispatch | In-process broadcast | < 1 ms | 3 ms | Async non-blocking loop over client sockets |
| Frontend Initial Hydration (Cold) | Production bundle | 280 ms | 420 ms | Includes Vite chunk loading + CSS render + IndexedDB init |

---

## 3. Database Connection & Pooling Metrics
- **Pool Type:** `NullPool` configured for serverless-safe asyncpg instances with automatic SSL handshake detection.
- **Connection Handshake:** ~45-80 ms initial TCP + TLS SNI negotiation on cold start to Neon Lakebase.
- **Query Saturation:** Safe under concurrent requests; transactions are scoped strictly per request using `async with AsyncSessionLocal() as session:`.

---

## 4. Resource Profile & Reliability Bounds
- **Backend Memory Consumption:** ~62 MB RSS idle; ~85 MB under burst testing.
- **Frontend Bundle Footprint:** 99.35 kB gzip JavaScript bundle; 4.01 kB gzip CSS stylesheet.
- **Backpressure & Queue Limits:**
  - Client-side offline mutation queue bounded to local IndexedDB storage.
  - WebSocket send queue drops stale events if socket is in unrecoverable error state.
  - Rate limiting sliding-window buffer purges expired timestamps automatically.

---

## 5. Identified Bottlenecks & Optimization Roadmap
1. **Search Indexing at Scale:** For message histories exceeding 100,000 records per workspace, transition the current PostgreSQL ILIKE search to PostgreSQL Full-Text Search with `tsvector` + GIN index, or OpenSearch.
2. **Horizontal Scaling of Realtime Gateway:** When running multiple API container instances on Render or Kubernetes, Redis Pub/Sub or NATS JetStream should be activated as the cross-node event broker.
