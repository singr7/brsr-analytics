from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from api.app.models.base import Base, Timestamped, UUIDPrimaryKey


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_user_ts", "user_id", "ts"),
        Index("ix_events_anon_ts", "anon_id", "ts"),
        {"postgresql_partition_by": "RANGE (ts)"},
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    anon_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    session_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    name: Mapped[str] = mapped_column(String(100))
    props_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)


class Lead(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "leads"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new','routed','contacted','qualified','closed')", name="status"
        ),
    )
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    org_id: Mapped[UUID | None] = mapped_column(ForeignKey("orgs.id"))
    score: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    signals_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(24), default="new")
    routed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str | None] = mapped_column(String(24))
    outcome_note: Mapped[str | None] = mapped_column(Text)
    route_attempts: Mapped[int] = mapped_column(Integer, default=0)
    route_error: Mapped[str | None] = mapped_column(Text)


class DeepdiveRequest(UUIDPrimaryKey, Timestamped, Base):
    __table_args__ = (
        CheckConstraint(
            "status IN ('new','scoped','quoted','delivered')", name="deepdive_status"
        ),
    )
    __tablename__ = "deepdive_requests"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    org_id: Mapped[UUID | None] = mapped_column(ForeignKey("orgs.id"))
    company_id: Mapped[UUID | None] = mapped_column(ForeignKey("companies.id"))
    request_text: Mapped[str] = mapped_column(Text)
    context_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(24), default="new")


class EventDailyAggregate(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "event_daily_aggregates"
    __table_args__ = (
        UniqueConstraint("day", "name", "dimension", "dimension_value"),
        Index("ix_event_daily_aggregates_day_name", "day", "name"),
    )
    day: Mapped[date] = mapped_column(Date)
    name: Mapped[str] = mapped_column(String(100))
    dimension: Mapped[str] = mapped_column(String(64), default="all")
    dimension_value: Mapped[str] = mapped_column(String(255), default="all")
    event_count: Mapped[int] = mapped_column(Integer, default=0)
