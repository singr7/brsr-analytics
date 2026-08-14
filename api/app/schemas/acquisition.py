from datetime import datetime
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
