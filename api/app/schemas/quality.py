from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class ReviewItem(BaseModel):
    review_id: UUID
    extracted_field_id: UUID
    field_key: str
    value_raw: str
    confidence: Decimal | None
    source_page: int | None
    source_quote: str | None
    page_image: str | None
    family: str
    confidence_band: str
    queued_at: datetime


class ReviewDecision(BaseModel):
    corrected_value: str | None = None
    corrected_numeric: Decimal | None = None
    corrected_unit: str | None = None


class ReviewResult(BaseModel):
    review_id: UUID
    status: str
    extracted_field_id: UUID
    pinned: bool
    policy_reasons: list[str]


class QualityFamily(BaseModel):
    family: str
    reviewed_count: int
    correct_count: int
    accuracy: Decimal


class QualityResponse(BaseModel):
    families: list[QualityFamily]
