from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from api.app.models.base import Base, Timestamped, UUIDPrimaryKey


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint("tier IN ('explore','pro','studio','research')", name="tier"),
    )
    tier: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    limits_json: Mapped[str] = mapped_column(Text, default="{}")


class User(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(String(160))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    plan_tier: Mapped[str] = mapped_column(ForeignKey("plans.tier"), default="explore")
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    analytics_opt_out: Mapped[bool] = mapped_column(Boolean, default=False)


class Org(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "orgs"
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    plan_tier: Mapped[str] = mapped_column(ForeignKey("plans.tier"), default="explore")
    seat_limit: Mapped[int] = mapped_column(Integer, default=1)
    licence_starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    licence_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    licence_grace_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Membership(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("org_id", "user_id"),
        CheckConstraint("role IN ('owner','member')", name="role"),
    )
    org_id: Mapped[UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16))


class ApiKey(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "api_keys"
    org_id: Mapped[UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    key_prefix: Mapped[str] = mapped_column(String(16), index=True)
    key_hash: Mapped[str] = mapped_column(Text, unique=True)
    scopes_json: Mapped[list[str]] = mapped_column(JSONB, default=list)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InvoiceRequest(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "invoice_requests"
    __table_args__ = (
        CheckConstraint("status IN ('requested','sent','paid','cancelled')", name="status"),
    )
    org_id: Mapped[UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    requested_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    requested_tier: Mapped[str] = mapped_column(ForeignKey("plans.tier"))
    seats: Mapped[int] = mapped_column(Integer)
    term_months: Mapped[int] = mapped_column(Integer)
    billing_email: Mapped[str] = mapped_column(String(320))
    status: Mapped[str] = mapped_column(String(24), default="requested")


class RefreshToken(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "refresh_tokens"
    jti: Mapped[UUID] = mapped_column(unique=True, index=True)
    family_id: Mapped[UUID] = mapped_column(index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_jti: Mapped[UUID | None]
    reuse_detected: Mapped[bool] = mapped_column(Boolean, default=False)


class EmailVerification(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "email_verifications"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OrgInvite(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "org_invites"
    __table_args__ = (CheckConstraint("role IN ('owner','member')", name="role"),)
    org_id: Mapped[UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    role: Mapped[str] = mapped_column(String(16), default="member")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
