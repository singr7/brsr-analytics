from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class FilingUploadResponse(BaseModel):
    filing_id: UUID
    company_id: UUID
    fy: int
    status: str
    source: str
    object_uri: str
    checksum_sha256: str
    deduplicated: bool
    acquired_at: datetime


class CoverageGroup(BaseModel):
    sector: str
    mcap_band: str
    companies: int
    fetched: int
    coverage_percent: float


class CoverageResponse(BaseModel):
    fy: int
    companies: int
    fetched: int
    coverage_percent: float
    groups: list[CoverageGroup]


class IngestionConfigSummary(BaseModel):
    source_enabled: bool
    schedule_enabled: bool
    refresh_hours: float
    default_fy: int
    default_batch_size: int
    next_offset: int


class IngestionRunSummary(BaseModel):
    id: UUID
    mode: str
    status: str
    target_fy: int
    requested_count: int
    fetched_count: int
    parsed_count: int
    missing_count: int
    error_count: int
    started_at: datetime
    completed_at: datetime | None


class FilingInventoryItem(BaseModel):
    company_id: UUID
    company_name: str
    ticker: str
    sector: str
    industry: str
    fy: int | None
    status: str
    source: str | None
    submission_date: date | None
    revision_date: date | None
    acquired_at: datetime | None
    raw_fact_count: int
    mapped_field_count: int
    source_url: str | None


class IngestionInventoryResponse(BaseModel):
    config: IngestionConfigSummary
    companies: int
    filings: int
    parsed_filings: int
    raw_facts: int
    items: list[FilingInventoryItem]
    recent_runs: list[IngestionRunSummary]
