FROM python:3.13-slim AS base

WORKDIR /app

COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY backend/app /app/backend/app

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "fastapi>=0.115.0" "uvicorn[standard]>=0.30.0" "sqlalchemy>=2.0.35" "asyncpg>=0.29.0" "alembic>=1.14.0" "pydantic>=2.7.0" "pydantic-settings>=2.3.0" "python-dotenv>=1.0.1" "argon2-cffi>=23.1.0"

EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
