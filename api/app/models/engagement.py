from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text
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


class DeepdiveRequest(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "deepdive_requests"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    org_id: Mapped[UUID | None] = mapped_column(ForeignKey("orgs.id"))
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"))
    request_text: Mapped[str] = mapped_column(Text)
    context_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(24), default="new")
