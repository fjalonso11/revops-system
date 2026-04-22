.PHONY: install dev test test-unit test-integration lint format typecheck db-migrate

install:
	pip install -e ".[dev]"

dev:
	uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

typecheck:
	mypy src/

db-migrate:
	psql "$(SUPABASE_DB_URL)" -f db/migrations/001_initial_schema.sql

db-local:
	docker compose up -d
