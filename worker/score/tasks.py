from __future__ import annotations

import asyncio

import redis.asyncio as redis

from api.app.core.config import get_settings
from api.app.db.session import create_engine, create_session_factory
from worker.celery_app import celery_app
from worker.score.materialize import rebuild_metrics


async def run_rebuild() -> tuple[int, int]:
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            result = await rebuild_metrics(session)
        client = redis.from_url(settings.redis_url)  # type: ignore[no-untyped-call]
        try:
            cursor = 0
            while True:
                cursor, keys = await client.scan(cursor, match="semantic:v*:*", count=250)
                if keys:
                    await client.delete(*keys)
                if cursor == 0:
                    break
        finally:
            await client.aclose()
        return result
    finally:
        await engine.dispose()


@celery_app.task(name="worker.score.rebuild")  # type: ignore[untyped-decorator]
def rebuild_metrics_task() -> tuple[int, int]:
    return asyncio.run(run_rebuild())


@celery_app.task(name="worker.score.pin_changed")  # type: ignore[untyped-decorator]
def pin_changed_task() -> tuple[int, int]:
    return asyncio.run(run_rebuild())
