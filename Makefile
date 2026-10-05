.PHONY: backend-install frontend-install up down lint test build

backend-install:
	cd backend && python -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -e .

frontend-install:
	cd frontend && npm install

up:
	docker compose up -d

down:
	docker compose down -v

lint:
	cd backend && python -m compileall app
	cd frontend && npm run build

test:
	cd backend && pytest -q
	cd frontend && npm test -- --run

build:
	docker compose build
