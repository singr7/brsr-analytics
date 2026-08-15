from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
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
    answers_revision: Mapped[int] = mapped_column(Integer, default=0)


class StudioDoc(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "studio_docs"
    studio_org_id: Mapped[UUID] = mapped_column(ForeignKey("studio_orgs.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(64))
    s3_uri: Mapped[str] = mapped_column(Text)
    parsed_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    filename: Mapped[str] = mapped_column(String(255), default="document")
    content_type: Mapped[str] = mapped_column(String(100), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)


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
    unit: Mapped[str | None] = mapped_column(String(32))
    evidence_doc_id: Mapped[UUID | None] = mapped_column(ForeignKey("studio_docs.id"))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    author: Mapped[str] = mapped_column(String(16))
    review_status: Mapped[str] = mapped_column(String(16), default="unreviewed")
    evidence_page: Mapped[int | None] = mapped_column(Integer)
    evidence_quote: Mapped[str | None] = mapped_column(Text)


class StudioProposal(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "studio_proposals"
    __table_args__ = (
        CheckConstraint(
            "review_status IN ('unreviewed','accepted','edited','rejected')",
            name="review_status",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence"),
    )
    studio_filing_id: Mapped[UUID] = mapped_column(
        ForeignKey("studio_filings.id", ondelete="CASCADE"), index=True
    )
    field_key: Mapped[str] = mapped_column(ForeignKey("field_defs.field_key"))
    value_raw: Mapped[str] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(String(32))
    evidence_doc_id: Mapped[UUID] = mapped_column(ForeignKey("studio_docs.id", ondelete="CASCADE"))
    evidence_page: Mapped[int] = mapped_column(Integer)
    evidence_quote: Mapped[str] = mapped_column(Text)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    review_status: Mapped[str] = mapped_column(String(16), default="unreviewed")
    decision_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))


class StudioComment(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "studio_comments"
    studio_filing_id: Mapped[UUID] = mapped_column(
        ForeignKey("studio_filings.id", ondelete="CASCADE"), index=True
    )
    field_key: Mapped[str] = mapped_column(ForeignKey("field_defs.field_key"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)


class StudioEditorLock(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "studio_editor_locks"
    __table_args__ = (UniqueConstraint("studio_filing_id"),)
    studio_filing_id: Mapped[UUID] = mapped_column(
        ForeignKey("studio_filings.id", ondelete="CASCADE")
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StudioExport(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "studio_exports"
    __table_args__ = (
        CheckConstraint("kind IN ('xbrl','docx','pdf','gap_pdf','package')", name="kind"),
        CheckConstraint("status IN ('queued','ready','blocked','failed')", name="status"),
    )
    studio_filing_id: Mapped[UUID] = mapped_column(
        ForeignKey("studio_filings.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(16))
    version: Mapped[int] = mapped_column(Integer)
    answers_revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    artifact_uri: Mapped[str | None] = mapped_column(Text)
    findings_json: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)
    stale: Mapped[bool] = mapped_column(Boolean, default=False)


class StudioTokenUsage(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "studio_token_usage"
    studio_org_id: Mapped[UUID] = mapped_column(
        ForeignKey("studio_orgs.id", ondelete="CASCADE"), index=True
    )
    prompt_key: Mapped[str] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
