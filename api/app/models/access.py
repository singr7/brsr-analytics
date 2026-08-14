from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint
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


class Org(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "orgs"
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    plan_tier: Mapped[str] = mapped_column(ForeignKey("plans.tier"), default="explore")


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
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
