from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from api.app.models.base import Base, Timestamped, UUIDPrimaryKey


class StudioOrg(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "studio_orgs"
    org_id: Mapped[UUID] = mapped_column(ForeignKey("orgs.id"), unique=True)
    legal_name: Mapped[str] = mapped_column(String(255))
    cin: Mapped[str | None] = mapped_column(String(21))


class StudioFiling(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "studio_filings"
    __table_args__ = (
        UniqueConstraint("studio_org_id", "fy"),
        CheckConstraint("status IN ('draft','review','final')", name="status"),
    )
    studio_org_id: Mapped[UUID] = mapped_column(ForeignKey("studio_orgs.id", ondelete="CASCADE"))
    fy: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    schema_version: Mapped[str] = mapped_column(String(32))


class StudioDoc(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "studio_docs"
    studio_org_id: Mapped[UUID] = mapped_column(ForeignKey("studio_orgs.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(64))
    s3_uri: Mapped[str] = mapped_column(Text)
    parsed_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)


class StudioAnswer(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "studio_answers"
    __table_args__ = (
        UniqueConstraint("studio_filing_id", "field_key"),
        CheckConstraint("author IN ('user','ai')", name="author"),
        CheckConstraint(
            "review_status IN ('unreviewed','accepted','edited','rejected')", name="review_status"
        ),
    )
    studio_filing_id: Mapped[UUID] = mapped_column(
        ForeignKey("studio_filings.id", ondelete="CASCADE")
    )
    field_key: Mapped[str] = mapped_column(ForeignKey("field_defs.field_key"))
    value_raw: Mapped[str] = mapped_column(Text)
    evidence_doc_id: Mapped[UUID | None] = mapped_column(ForeignKey("studio_docs.id"))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    author: Mapped[str] = mapped_column(String(16))
    review_status: Mapped[str] = mapped_column(String(16), default="unreviewed")
