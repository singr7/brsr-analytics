.PHONY: bootstrap up down verify test-api test-worker test-fe migrate seed ingest-nse-initial ingest-nse-next ingest-nse-refresh publish-nse rebuild-metrics fetch-testdata bench-extraction lint-schema fmt

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
	$(PYTHON) -m worker.studio.schema
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

NSE_FY ?= 2025
NSE_LIMIT ?= 10

ingest-nse-initial:
	$(PYTHON) -m worker.acquire.cli initial --fy $(NSE_FY) --limit 25 --replace-synthetic --publish

ingest-nse-next:
	$(PYTHON) -m worker.acquire.cli next --fy $(NSE_FY) --limit $(NSE_LIMIT) --publish

ingest-nse-refresh:
	$(PYTHON) -m worker.acquire.cli refresh --fy $(NSE_FY) --limit $(NSE_LIMIT) --publish

publish-nse:
	$(PYTHON) -m worker.acquire.cli publish --fy $(NSE_FY)
	$(PYTHON) -m worker.score.cli

rebuild-metrics:
	$(PYTHON) -m worker.score.cli

fetch-testdata:
	$(PYTHON) -m worker.parse.fixtures

bench-extraction:
	$(PYTHON) -m worker.extract.benchmark

lint-schema:
	$(PYTHON) -m worker.studio.schema
