NPM = $(shell node -p "process.platform === 'win32' ? 'npm.cmd' : 'npm'")

.PHONY: backend-install frontend-install up down lint test build

backend-install:
	cd backend && python -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -e '.[dev]'

frontend-install:
	cd frontend && $(NPM) install

up:
	docker compose up -d

down:
	docker compose down -v

lint:
	cd backend && python -m compileall app
	cd frontend && $(NPM) run build

test:
	pytest -q tests
	cd frontend && $(NPM) test -- --run

build:
	docker compose build
