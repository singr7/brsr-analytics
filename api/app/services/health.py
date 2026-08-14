from collections.abc import Awaitable, Callable
from typing import Literal

import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from api.app.core.config import Settings
from api.app.schemas.health import DependencyHealth, HealthResponse

HealthCheck = Callable[[], Awaitable[None]]


async def _database_check(settings: Settings) -> None:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    finally:
        await engine.dispose()


async def _redis_check(settings: Settings) -> None:
    client = redis.from_url(settings.redis_url)  # type: ignore[no-untyped-call]
    try:
        await client.ping()
    finally:
        await client.aclose()


async def _run(check: HealthCheck) -> DependencyHealth:
    try:
        await check()
        return DependencyHealth(status="ok")
    except Exception as exc:  # health endpoint must report dependency failures
        return DependencyHealth(status="error", detail=type(exc).__name__)


async def get_health(
    settings: Settings,
    database_check: HealthCheck | None = None,
    redis_check: HealthCheck | None = None,
) -> HealthResponse:
    async def default_database() -> None:
        await _database_check(settings)

    async def default_redis() -> None:
        await _redis_check(settings)

    database = await _run(database_check or default_database)
    redis_health = await _run(redis_check or default_redis)
    llm = DependencyHealth(
        status="ok" if settings.llm_config_present else "error",
        detail=None if settings.llm_config_present else "missing API key",
    )
    overall: Literal["ok", "degraded"] = (
        "ok" if all(x.status == "ok" for x in (database, redis_health, llm)) else "degraded"
    )
    return HealthResponse(status=overall, database=database, redis=redis_health, llm_config=llm)
