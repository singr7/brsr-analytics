from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from api.app.core.config import Settings, get_settings
from api.app.db.session import create_engine, create_session_factory
from api.app.services.storage import object_store
from worker.acquire.adapters import (
    AcquisitionDisabledError,
    CompanyIRAdapter,
    ExchangeAnnouncementAdapter,
    ExchangeXbrlAdapter,
    SourceAdapter,
)
from worker.acquire.nse import ingest_nse_batch
from worker.acquire.service import acquire_one
from worker.celery_app import celery_app


def configured_adapters(settings: Settings) -> dict[str, SourceAdapter]:
    return {
        "exchange_xbrl": ExchangeXbrlAdapter(
            enabled=settings.source_exchange_xbrl_enabled,
            url_template=settings.source_exchange_xbrl_url_template,
            rate_per_second=settings.acquisition_rate_per_second,
        ),
        "exchange_announcements": ExchangeAnnouncementAdapter(
            enabled=settings.source_exchange_announcements_enabled,
            url_template=settings.source_exchange_announcements_url_template,
            rate_per_second=settings.acquisition_rate_per_second,
        ),
        "company_ir": CompanyIRAdapter(
            enabled=settings.source_company_ir_enabled,
            rate_per_second=settings.acquisition_rate_per_second,
        ),
    }


async def run_acquisition(company_id: UUID, fy: int, source_adapter: str) -> str:
    settings = get_settings()
    adapter = configured_adapters(settings).get(source_adapter)
    if adapter is None:
        raise ValueError(f"Unknown source adapter: {source_adapter}")
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            filing = await acquire_one(
                session, object_store(settings), adapter, company_id=company_id, fy=fy
            )
            return str(filing.id)
    finally:
        await engine.dispose()


@celery_app.task(bind=True, name="worker.acquire.company_fy")  # type: ignore[untyped-decorator]
def acquire_company_fy(self: Any, company_id: str, fy: int, source_adapter: str) -> str:
    """Resume-safe company-FY orchestration; transient failures use bounded backoff."""
    try:
        return asyncio.run(run_acquisition(UUID(company_id), fy, source_adapter))
    except AcquisitionDisabledError:
        raise
    except Exception as exc:
        settings = get_settings()
        raise self.retry(
            exc=exc,
            countdown=min(300, 2 ** (self.request.retries + 1)),
            max_retries=settings.acquisition_max_attempts - 1,
        ) from exc


async def run_nse_refresh() -> str:
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            run = await ingest_nse_batch(
                session,
                object_store(settings),
                settings,
                mode="refresh",
                target_fy=settings.nse_brsr_default_fy,
                limit=settings.nse_brsr_default_batch_size,
            )
            return str(run.id)
    finally:
        await engine.dispose()


@celery_app.task(name="worker.acquire.nse_refresh")  # type: ignore[untyped-decorator]
def nse_refresh() -> str:
    return asyncio.run(run_nse_refresh())
