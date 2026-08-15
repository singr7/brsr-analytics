from __future__ import annotations

import asyncio
from uuid import UUID

from api.app.core.config import get_settings
from api.app.db.session import create_engine, create_session_factory
from api.app.services.storage import object_store
from worker.celery_app import celery_app
from worker.parse.service import parse_filing


async def run_parse(filing_id: UUID) -> str:
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            filing = await parse_filing(
                session,
                object_store(settings),
                filing_id,
                embedding_model=settings.embedding_model,
            )
            return str(filing.id)
    finally:
        await engine.dispose()


@celery_app.task(name="worker.parse.filing")  # type: ignore[untyped-decorator]
def parse_filing_task(filing_id: str) -> str:
    return asyncio.run(run_parse(UUID(filing_id)))
