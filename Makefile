.PHONY: bootstrap up down verify test-api test-worker test-fe migrate seed rebuild-metrics fetch-testdata bench-extraction fmt

PYTHON := .venv/bin/python
RUFF := .venv/bin/ruff
MYPY := .venv/bin/mypy
PYTEST := .venv/bin/pytest

bootstrap:
	uv sync --extra dev
	pnpm --dir frontend install --frozen-lockfile

up:
	test -f .env || cp .env.example .env
	docker compose up --build -d

down:
	docker compose down

verify:
	$(RUFF) check api worker
	$(MYPY)
	$(PYTEST) api/tests worker/tests
	pnpm --dir frontend exec tsc -b
	pnpm --dir frontend run lint
	pnpm --dir frontend run test

test-api:
	$(PYTEST) api/tests

test-worker:
	$(PYTEST) worker/tests

test-fe:
	pnpm --dir frontend run test

fmt:
	$(RUFF) format api worker
	$(RUFF) check --fix api worker
	pnpm --dir frontend exec eslint src --ext ts,tsx --fix

migrate:
	$(PYTHON) -m alembic upgrade head

seed:
	$(PYTHON) -m api.app.db.seed

rebuild-metrics:
	$(PYTHON) -m worker.score.cli

fetch-testdata:
	$(PYTHON) -m worker.parse.fixtures

bench-extraction:
	$(PYTHON) -m worker.extract.benchmark
