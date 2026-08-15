from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class DeepdiveCreate(BaseModel):
    question: str = Field(min_length=20, max_length=4000)
    company_ids: list[UUID] = Field(min_length=1, max_length=20)
    timeframe: str = Field(min_length=2, max_length=120)
    budget_band: str = Field(pattern=r"^(under_1l|1l_3l|3l_5l|5l_plus|unsure)$")
    contact_email: EmailStr


class CompanyOption(BaseModel):
    id: UUID
    name: str
    sector: str


class DeepdiveItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    org_id: UUID | None
    company_ids: list[UUID]
    question: str
    timeframe: str
    budget_band: str
    contact_email: str
    status: str
    created_at: datetime


class DeepdiveStatusUpdate(BaseModel):
    status: str = Field(pattern=r"^(new|scoped|quoted|delivered)$")


class LeadSignal(BaseModel):
    key: str
    label: str
    occurred_at: datetime
    points: int
    properties: dict[str, object]


class LeadItem(BaseModel):
    id: UUID
    user_id: UUID | None
    org_id: UUID | None
    score: float
    signals: list[LeadSignal]
    status: str
    routed_at: datetime | None
    outcome: str | None
    outcome_note: str | None


class LeadOutcomeUpdate(BaseModel):
    outcome: str = Field(pattern=r"^(qualified|meeting|proposal|won|lost|not_a_fit)$")
    note: str | None = Field(default=None, max_length=2000)


class FunnelStep(BaseModel):
    name: str
    users: int
    conversion_from_previous: float | None


class AnalyticsCount(BaseModel):
    name: str
    count: int


class AnalyticsResponse(BaseModel):
    generated_at: datetime
    range_start: datetime
    visit_to_pro: list[FunnelStep]
    studio_to_export: list[FunnelStep]
    feature_usage: list[AnalyticsCount]
    nlq_themes: list[AnalyticsCount]
    sector_interest: list[AnalyticsCount]


class LeadQualitySignal(BaseModel):
    signal: str
    leads: int
    positive_outcomes: int
    conversion_rate: float


class LeadQualityResponse(BaseModel):
    generated_at: datetime
    by_signal: list[LeadQualitySignal]


class PrivacyPreference(BaseModel):
    analytics_enabled: bool


class RetentionResult(BaseModel):
    cutoff: date
    aggregated: int
    deleted: int
