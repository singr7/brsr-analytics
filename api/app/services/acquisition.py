import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.config import Settings
from api.app.models import Company, ExtractedField, Filing, IngestionRun, IngestionState, XbrlFact
from api.app.schemas.acquisition import (
    CoverageGroup,
    CoverageResponse,
    FilingInventoryItem,
    IngestionConfigSummary,
    IngestionInventoryResponse,
    IngestionRunSummary,
)
from api.app.services.storage import ObjectStore, raw_filing_key


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    uri: str
    checksum_sha256: str
    deduplicated: bool


def validate_artifact(filename: str, content: bytes) -> tuple[str, str]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf" and content.startswith(b"%PDF-"):
        return "pdf", "application/pdf"
    if suffix in {".xbrl", ".xml"} and content.lstrip().startswith(b"<"):
        return "xbrl", "application/xml"
    raise ValueError("Artifact content does not match a supported .pdf, .xbrl, or .xml filename")


async def store_filing(
    session: AsyncSession,
    store: ObjectStore,
    *,
    company: Company,
    fy: int,
    filename: str,
    content: bytes,
    source: str,
    source_adapter: str,
    source_url: str | None = None,
) -> tuple[Filing, StoredArtifact]:
    artifact_type, media_type = validate_artifact(filename, content)
    if source != "manual" and source != artifact_type:
        raise ValueError("Adapter source type does not match artifact")
    checksum = hashlib.sha256(content).hexdigest()
    existing = await session.scalar(
        select(Filing).where(Filing.company_id == company.id, Filing.fy == fy)
    )
    if existing and existing.checksum_sha256 == checksum and existing.s3_raw:
        return existing, StoredArtifact(existing.s3_raw, checksum, True)

    key = raw_filing_key(company.cin, fy, filename)
    uri = store.put(key, content, media_type)
    filing = existing or Filing(company_id=company.id, fy=fy, source=source)
    filing.source = source
    filing.s3_raw = uri
    filing.status = "fetched"
    filing.acquired_at = datetime.now(UTC)
    filing.source_adapter = source_adapter
    filing.source_url = source_url
    filing.filename = Path(filename).name
    filing.checksum_sha256 = checksum
    filing.acquisition_attempts = (filing.acquisition_attempts or 0) + 1
    filing.acquisition_error = None
    session.add(filing)
    await session.commit()
    await session.refresh(filing)
    return filing, StoredArtifact(uri, checksum, False)


async def coverage(session: AsyncSession, fy: int) -> CoverageResponse:
    fetched = func.count(case((Filing.status == "fetched", 1)))
    query = (
        select(
            Company.sector,
            Company.mcap_band,
            func.count(Company.id),
            fetched,
        )
        .outerjoin(Filing, and_(Filing.company_id == Company.id, Filing.fy == fy))
        .group_by(Company.sector, Company.mcap_band)
        .order_by(Company.sector, Company.mcap_band)
    )
    rows = (await session.execute(query)).all()
    groups = [
        CoverageGroup(
            sector=sector,
            mcap_band=band,
            companies=company_count,
            fetched=fetched_count,
            coverage_percent=round(100 * fetched_count / company_count, 2),
        )
        for sector, band, company_count, fetched_count in rows
    ]
    company_count = sum(group.companies for group in groups)
    fetched_count = sum(group.fetched for group in groups)
    return CoverageResponse(
        fy=fy,
        companies=company_count,
        fetched=fetched_count,
        coverage_percent=round(100 * fetched_count / company_count, 2) if company_count else 0,
        groups=groups,
    )


async def ingestion_inventory(
    session: AsyncSession, settings: Settings
) -> IngestionInventoryResponse:
    raw_count = (
        select(func.count(XbrlFact.id))
        .where(XbrlFact.filing_id == Filing.id)
        .correlate(Filing)
        .scalar_subquery()
    )
    mapped_count = (
        select(func.count(ExtractedField.id))
        .where(ExtractedField.filing_id == Filing.id)
        .correlate(Filing)
        .scalar_subquery()
    )
    rows = (
        await session.execute(
            select(Company, Filing, raw_count, mapped_count)
            .outerjoin(Filing, Filing.company_id == Company.id)
            .order_by(Company.name, Filing.fy.desc())
        )
    ).all()
    state = await session.get(IngestionState, "nse_brsr")
    recent = (
        await session.scalars(
            select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(10)
        )
    ).all()
    items = [
        FilingInventoryItem(
            company_id=company.id,
            company_name=company.name,
            ticker=company.ticker,
            sector=company.sector,
            industry=company.industry,
            fy=filing.fy if filing else None,
            status=filing.status if filing else "registered",
            source=filing.source if filing else None,
            submission_date=filing.submission_date if filing else None,
            revision_date=filing.revision_date if filing else None,
            acquired_at=filing.acquired_at if filing else None,
            raw_fact_count=int(raw_facts or 0),
            mapped_field_count=int(mapped_fields or 0),
            source_url=filing.source_url if filing else None,
        )
        for company, filing, raw_facts, mapped_fields in rows
    ]
    return IngestionInventoryResponse(
        config=IngestionConfigSummary(
            source_enabled=settings.source_nse_brsr_enabled,
            schedule_enabled=settings.nse_brsr_schedule_enabled,
            refresh_hours=settings.nse_brsr_refresh_hours,
            default_fy=settings.nse_brsr_default_fy,
            default_batch_size=settings.nse_brsr_default_batch_size,
            next_offset=state.next_offset if state else 0,
        ),
        companies=len({item.company_id for item in items}),
        filings=sum(item.fy is not None for item in items),
        parsed_filings=sum(item.status == "parsed" for item in items),
        raw_facts=sum(item.raw_fact_count for item in items),
        items=items,
        recent_runs=[
            IngestionRunSummary(
                id=run.id,
                mode=run.mode,
                status=run.status,
                target_fy=run.target_fy,
                requested_count=run.requested_count,
                fetched_count=run.fetched_count,
                parsed_count=run.parsed_count,
                missing_count=run.missing_count,
                error_count=run.error_count,
                started_at=run.started_at,
                completed_at=run.completed_at,
            )
            for run in recent
        ],
    )
