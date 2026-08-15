from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from api.app.core.config import get_settings
from api.app.db.session import create_engine, create_session_factory
from api.app.services.llm import get_llm
from worker.celery_app import celery_app
from worker.extract.run import run_extraction


async def run_extract(filing_id: UUID) -> int:
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            return await run_extraction(
                session,
                filing_id,
                get_llm(settings),
                attempts=settings.extraction_max_attempts,
            )
    finally:
        await engine.dispose()


@celery_app.task(bind=True, name="worker.extract.filing")  # type: ignore[untyped-decorator]
def extract_filing_task(self: Any, filing_id: str) -> int:
    try:
        return asyncio.run(run_extract(UUID(filing_id)))
    except Exception as exc:
        settings = get_settings()
        raise self.retry(
            exc=exc,
            countdown=min(300, 2 ** (self.request.retries + 1)),
            max_retries=settings.extraction_max_attempts - 1,
        ) from exc
