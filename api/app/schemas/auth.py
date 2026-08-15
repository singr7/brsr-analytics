from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=1, max_length=160)


class LoginRequest(BaseModel):
    # Seed/demo accounts intentionally use the RFC-reserved ``.local`` suffix.
    email: str = Field(min_length=3, max_length=320)
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class VerifyRequest(BaseModel):
    token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class SignupResponse(BaseModel):
    user_id: UUID
    verification_token: str | None = None


class OrgSummary(BaseModel):
    id: UUID
    name: str
    slug: str
    role: str
    plan_tier: str


class MeResponse(BaseModel):
    id: UUID
    email: str
    display_name: str
    email_verified_at: datetime | None
    plan_tier: str
    is_admin: bool
    orgs: list[OrgSummary]


class CreateOrgRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)


class InviteRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="member", pattern=r"^(owner|member)$")


class InviteResponse(BaseModel):
    invite_id: UUID
    invite_token: str | None = None


class AcceptInviteRequest(BaseModel):
    token: str


class PlanChangeRequest(BaseModel):
    tier: str = Field(pattern=r"^(explore|pro|studio|research)$")


class MessageResponse(BaseModel):
    message: str


class EventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    properties: dict[str, object] = Field(default_factory=dict)
    session_id: UUID
    occurred_at: datetime | None = None


class EventBatch(BaseModel):
    events: list[EventInput] = Field(min_length=1, max_length=50)
