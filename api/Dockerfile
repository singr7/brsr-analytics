FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev
COPY alembic.ini ./alembic.ini
COPY api ./api
COPY worker ./worker
COPY prompts ./prompts
COPY taxonomy ./taxonomy
COPY events.yaml ./events.yaml
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app
CMD ["uvicorn", "api.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
