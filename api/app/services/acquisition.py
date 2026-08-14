import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.models import Company, Filing
from api.app.schemas.acquisition import CoverageGroup, CoverageResponse
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
