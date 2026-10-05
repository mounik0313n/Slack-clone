# Production hosting guide

This project is designed for a layered deployment model:

- Frontend: Vite static site, served behind Nginx or a CDN
- Backend: FastAPI app behind a reverse proxy and TLS termination
- Database: PostgreSQL as the system of record
- Session / hot cache: Redis
- Messaging / event backbone: NATS
- Search: OpenSearch
- File storage: MinIO or S3

## Recommended topology

### Option A: simplest production deployment
Use managed services:

- Frontend: Vercel or Netlify
- Backend: Render, Railway, Fly.io, Azure App Service, or a Docker VPS
- Database: Neon, Supabase Postgres, Azure Database for PostgreSQL, or RDS
- Redis: Upstash, Azure Cache for Redis, or ElastiCache
- NATS: self-hosted or managed NATS service
- Object storage: S3-compatible bucket or MinIO

### Option B: full self-hosted deployment
Use a Linux VPS or Kubernetes cluster:

- reverse proxy: Nginx + TLS via Let's Encrypt
- frontend build: static files from `frontend/dist`
- API: `uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`
- PostgreSQL on a managed VM/service
- Redis and NATS on separate containers or services
- MinIO or S3 for file attachments

## Exact hosting flow

### 1) Frontend hosting

Build the frontend for production:

```bash
cd frontend
npm install
npm run build
```

This creates the `frontend/dist` directory.

Serve it through Nginx or a static host.

Example Nginx config:

```nginx
server {
    listen 80;
    server_name app.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name app.example.com;

    ssl_certificate /etc/letsencrypt/live/app.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.example.com/privkey.pem;

    root /var/www/slack-frontend/dist;
    index index.html;

    location / {
        try_files $uri /index.html;
    }
}
```

If you use Vercel or Netlify, set:

- `VITE_API_URL=https://api.example.com`
- `VITE_WS_URL=wss://api.example.com/ws`

### 2) Backend API hosting

Run the backend from the repo root:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Create a production `.env` file using `.env.production.example` as reference.

Then start the app with:

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

Example systemd service:

```ini
[Unit]
Description=Slack Platform API
After=network.target

[Service]
WorkingDirectory=/opt/slack-platform
EnvironmentFile=/opt/slack-platform/.env
ExecStart=/opt/slack-platform/backend/.venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Place the app behind Nginx on the same server or a load balancer.

### 3) Database hosting

Use PostgreSQL 16+ in a managed or self-hosted setup.

Example connection string:

```env
DATABASE_URL=postgresql+asyncpg://postgres:STRONG_PASSWORD@db.example.com:5432/slack_platform
```

Recommended settings:

- 2 vCPU / 4 GB RAM minimum for small teams
- daily backups enabled
- automated failover enabled for production
- connection pooling enabled if traffic increases

### 4) Redis hosting

Redis is used for hot state and presence.

Example:

```env
REDIS_URL=redis://:STRONG_REDIS_PASSWORD@redis.example.com:6379/0
```

Recommended:

- dedicated Redis instance
- TLS enabled for public endpoints
- persistence enabled for recovery

### 5) NATS hosting

NATS is the event backbone and durable messaging layer.

Example:

```env
NATS_URL=nats://nats.example.com:4222
```

Recommended:

- run NATS in clustered mode in production
- enable JetStream persistence
- keep a separate stream config for realtime and notifications

### 6) Object storage

The project supports MinIO or S3-compatible storage.

For MinIO:

```bash
docker run -d \
  --name minio \
  -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=your_user \
  -e MINIO_ROOT_PASSWORD=your_password \
  -v minio_data:/data \
  minio/minio server /data --console-address ":9001"
```

For AWS S3, set the endpoint and bucket variables to your provider-specific values.

### 7) TLS and domains

Recommended domain layout:

- `app.example.com` → frontend
- `api.example.com` → backend
- `storage.example.com` → MinIO or S3 endpoint
- `meet.example.com` → LiveKit / media service if used

Obtain certificates with Let's Encrypt:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d api.example.com -d app.example.com
```

### 8) Production environment file

Use the example file as a base:

```bash
cp .env.production.example .env
```

Then fill in all secrets before starting the API in production.

### 9) Recommended deployment order

1. PostgreSQL
2. Redis
3. NATS
4. OpenSearch / MinIO
5. Backend API
6. Frontend build and CDN
7. health checks and TLS
8. production smoke tests

## Health checks

The app exposes:

- `GET /health`
- `GET /health/live`
- `GET /health/ready`

Use these for load balancer checks and deployment gating.

## Production security checklist

- use real secrets, not placeholders
- restrict CORS to your frontend domain
- enable HTTPS everywhere
- store secrets in a vault or GitHub Actions secrets
- enable DB backups
- restrict database network access to app servers only
- rotate tokens and passwords on a schedule
- set `APP_ENV=production`

## Best simple deployment option

If you want the least-friction production deployment:

- Frontend: Vercel
- Backend: Render or Railway
- Database: Supabase / Neon
- Redis: Upstash
- Storage: AWS S3
- Message bus: managed NATS or keep local if infra can support it

This gives you a clean, production-ready stack with minimal ops work.
