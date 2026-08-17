# Production image for the API, the Celery worker and the Beat scheduler.
# One image, three commands, chosen in compose.prod.yml.
#
# Differences from api/Dockerfile, which stays the local development image:
#   * multi-stage, so uv and the build toolchain never reach the runtime layer;
#   * runs as a non-root user;
#   * no --reload, and no source bind mount at run time.
#
# Build from the repository root:
#   docker build -f infra/deploy/api.Dockerfile -t <registry>/brsrlens/api:<tag> .

# --- dependencies -----------------------------------------------------------
FROM python:3.12-slim AS deps

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
# --frozen fails rather than silently resolving a different tree than CI tested.
RUN uv sync --frozen --no-dev --no-install-project

# --- runtime ----------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app

# libgomp1 is required by PyMuPDF; curl is used by the container healthcheck and
# by the deploy script's readiness probe.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin brsrlens

WORKDIR /app

COPY --from=deps /app/.venv /app/.venv

COPY alembic.ini ./alembic.ini
COPY api ./api
COPY worker ./worker
COPY ops ./ops
COPY prompts ./prompts
COPY taxonomy ./taxonomy
COPY events.yaml scoring.yaml plans.yaml leads.yaml ./

# Writable state: the object-store fallback root and the Beat schedule file.
# Only .data needs ownership; chowning the venv would duplicate the whole layer.
RUN mkdir -p /app/.data && chown -R brsrlens:brsrlens /app/.data

USER brsrlens

EXPOSE 8000

# Overridden per service in compose.prod.yml. This default is the API.
CMD ["uvicorn", "api.app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
