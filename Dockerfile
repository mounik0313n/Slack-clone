FROM python:3.13-slim AS base

WORKDIR /app

COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY backend/requirements.txt /app/backend/requirements.txt
COPY backend/alembic.ini /app/backend/alembic.ini
COPY backend/migrations /app/backend/migrations
COPY backend/app /app/backend/app
COPY backend/main.py /app/backend/main.py

ENV PYTHONPATH=/app/backend:/app

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/backend/requirements.txt && \
    pip install --no-cache-dir -e /app/backend

EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
