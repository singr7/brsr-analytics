# HANDOFF — after S01 (2026-08-14)

## Repo state: `main` · dev services up · migrations not introduced (S02)

## Delivered

- Python 3.12 FastAPI and Celery skeletons with uv-locked dependencies.
- `/healthz` checks Postgres, Redis, and LLM configuration; failures return 503.
- JSON logs, propagated/generated `X-Request-ID`, CORS, and typed health contracts.
- Provider-neutral LLM interface with an offline FakeLLM prompt/fixture round trip.
- Registered in-memory product-event sink; unknown event names fail immediately.
- React 18/Vite/Tailwind/ECharts shell, health footer, Compose stack, and CI verify job.

## Contracts next session relies on

- Services/ports: `postgres:5432`, `redis:6379`, `api:8000`, `frontend:5173`,
  `mailhog:1025/8025`; host ports are configurable independently.
- LLM: `LLMClient.complete(prompt_key, version, variables, schema) -> parsed` (async).
- Factory: `api.app.services.llm.get_llm(settings=None) -> LLMClient`.
- Prompts: `prompts/{prompt_key}.yaml`; fixtures:
  `prompts/fixtures/{prompt_key}@{version}/{case}.json`.
- Health: `GET /healthz -> HealthResponse`; status is `ok` or `degraded`.
- Tracking: `Tracker.track(name, properties=None)`; registry is `events.yaml`.
- Worker entry: `worker.celery_app:celery_app`; health task is `worker.healthcheck`.

## Sharp edges

- Database models and Alembic migration are intentionally deferred to S02.
- Tracking is intentionally in-memory until the S02 events table exists.
- Live LLM calls require both `LLM_NETWORK_ENABLED=true` and `LLM_API_KEY`.
- MailHog uses amd64 emulation on Apple Silicon.
- Local ports may need `.env` overrides when other projects are running.

## Env/secrets added

`APP_ENV`, `LOG_LEVEL`, `API_HOST`, `API_PORT`, `FRONTEND_PORT`, `POSTGRES_DB`,
`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_PORT`, `DATABASE_URL`, `REDIS_URL`,
`REDIS_PORT`, `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`,
`LLM_FIXTURE_CASE`, `LLM_NETWORK_ENABLED`, `VITE_API_URL`.

## Next: S02 — expected entry state

Run `make up`; add SQLAlchemy models and the initial Alembic migration against the
healthy pgvector/Postgres service. Keep public-value pin semantics in the schema.
