FROM python:3.13-slim AS base

WORKDIR /app

COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY backend/app /app/backend/app

ENV PYTHONPATH=/app/backend:/app

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e /app/backend

EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
