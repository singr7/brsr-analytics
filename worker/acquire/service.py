from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.models import AcquisitionCursor, Company, Filing
from api.app.services.acquisition import store_filing
from api.app.services.storage import ObjectStore
from worker.acquire.adapters import CompanyRef, FetchResult, SourceAdapter


async def acquire_one(
    session: AsyncSession,
    store: ObjectStore,
    adapter: SourceAdapter,
    company_id: UUID,
    fy: int,
) -> Filing:
    company = await session.get(Company, company_id)
    if company is None:
        raise ValueError("Company not found")
    cursor_row = await session.scalar(
        select(AcquisitionCursor).where(
            AcquisitionCursor.source_adapter == adapter.name,
            AcquisitionCursor.company_id == company_id,
            AcquisitionCursor.fy == fy,
        )
    )
    cursor = cursor_row.cursor_json if cursor_row else {}
    try:
        result = adapter.fetch(
            CompanyRef(company.cin, company.ticker, company.exchange, company.ir_url), fy, cursor
        )
        await _save_cursor(session, cursor_row, adapter.name, company_id, fy, result)
        if result.status == "fetched":
            if result.content is None or result.filename is None:
                raise ValueError("Adapter returned fetched without content and filename")
            filing, _ = await store_filing(
                session,
                store,
                company=company,
                fy=fy,
                filename=result.filename,
                content=result.content,
                source=adapter.artifact_type,
                source_adapter=adapter.name,
                source_url=result.source_url,
            )
            return filing
        return await _record_status(session, company_id, fy, adapter, "missing", None)
    except Exception as exc:
        await session.rollback()
        await _record_status(session, company_id, fy, adapter, "error", str(exc)[:2000])
        raise


async def _save_cursor(
    session: AsyncSession,
    row: AcquisitionCursor | None,
    source_adapter: str,
    company_id: UUID,
    fy: int,
    result: FetchResult,
) -> None:
    cursor = row or AcquisitionCursor(
        source_adapter=source_adapter, company_id=company_id, fy=fy, cursor_json={}
    )
    cursor.cursor_json = result.cursor
    session.add(cursor)
    await session.commit()


async def _record_status(
    session: AsyncSession,
    company_id: UUID,
    fy: int,
    adapter: SourceAdapter,
    status: str,
    error: str | None,
) -> Filing:
    filing = await session.scalar(
        select(Filing).where(Filing.company_id == company_id, Filing.fy == fy)
    )
    if filing is None:
        filing = Filing(company_id=company_id, fy=fy, source=adapter.artifact_type)
    filing.status = status
    filing.source_adapter = adapter.name
    filing.acquisition_attempts = (filing.acquisition_attempts or 0) + 1
    filing.acquisition_error = error
    session.add(filing)
    await session.commit()
    await session.refresh(filing)
    return filing
