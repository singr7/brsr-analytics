from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class LicenceChange(BaseModel):
    tier: Literal["explore", "pro", "studio", "research"]
    seats: int = Field(ge=1, le=500)
    starts_at: datetime
    expires_at: datetime
    grace_days: int = Field(default=14, ge=0, le=90)


class LicenceSummary(BaseModel):
    org_id: UUID
    tier: str
    seats: int
    starts_at: datetime | None
    expires_at: datetime | None
    grace_until: datetime | None
    state: Literal["active", "grace", "read_only"]


class InvoiceCreate(BaseModel):
    tier: Literal["pro", "studio", "research"]
    seats: int = Field(ge=1, le=500)
    term_months: int = Field(default=12, ge=1, le=36)
    billing_email: EmailStr


class InvoiceSummary(BaseModel):
    id: UUID
    status: str
    delivery: Literal["manual_invoice"] = "manual_invoice"


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    scopes: list[Literal["query:read", "dataset:read"]] = Field(min_length=1, max_length=2)


class ApiKeyCreated(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    scopes: list[str]
    secret: str


class ApiKeySummary(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    scopes: list[str]
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None
