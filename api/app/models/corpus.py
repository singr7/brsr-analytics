from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from api.app.models.base import Base, Timestamped, UUIDPrimaryKey


class Company(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "companies"
    __table_args__ = (CheckConstraint("mcap_band IN ('large','mid','small')", name="mcap_band"),)
    cin: Mapped[str] = mapped_column(String(21), unique=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    ticker: Mapped[str] = mapped_column(String(32), unique=True)
    exchange: Mapped[str] = mapped_column(String(16))
    sector: Mapped[str] = mapped_column(String(100), index=True)
    industry: Mapped[str] = mapped_column(String(160))
    mcap_band: Mapped[str] = mapped_column(String(16), index=True)
    ir_url: Mapped[str | None] = mapped_column(Text)


class Filing(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "filings"
    __table_args__ = (
        UniqueConstraint("company_id", "fy", name="uq_filings_company_fy"),
        CheckConstraint("source IN ('xbrl','pdf','manual')", name="source"),
    )
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    fy: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(16))
    s3_raw: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="missing")
    acquired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_adapter: Mapped[str | None] = mapped_column(String(64))
    source_url: Mapped[str | None] = mapped_column(Text)
    filename: Mapped[str | None] = mapped_column(String(255))
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    acquisition_attempts: Mapped[int] = mapped_column(Integer, default=0)
    acquisition_error: Mapped[str | None] = mapped_column(Text)
    submission_date: Mapped[date | None] = mapped_column(Date)
    revision_date: Mapped[date | None] = mapped_column(Date)
    parse_version: Mapped[int] = mapped_column(Integer, default=0)
    parsed_pages: Mapped[int] = mapped_column(Integer, default=0)
    sections_found: Mapped[int] = mapped_column(Integer, default=0)
    xbrl_fact_count: Mapped[int] = mapped_column(Integer, default=0)
    section_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AcquisitionCursor(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "acquisition_cursors"
    __table_args__ = (UniqueConstraint("source_adapter", "company_id", "fy"),)
    source_adapter: Mapped[str] = mapped_column(String(64))
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    fy: Mapped[int] = mapped_column(Integer)
    cursor_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)


class IngestionRun(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "ingestion_runs"
    source: Mapped[str] = mapped_column(String(64), index=True)
    mode: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24), index=True)
    target_fy: Mapped[int] = mapped_column(Integer)
    batch_start: Mapped[int] = mapped_column(Integer, default=0)
    requested_count: Mapped[int] = mapped_column(Integer)
    discovered_count: Mapped[int] = mapped_column(Integer, default=0)
    fetched_count: Mapped[int] = mapped_column(Integer, default=0)
    parsed_count: Mapped[int] = mapped_column(Integer, default=0)
    missing_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IngestionState(Timestamped, Base):
    __tablename__ = "ingestion_state"
    source: Mapped[str] = mapped_column(String(64), primary_key=True)
    next_offset: Mapped[int] = mapped_column(Integer, default=0)
    state_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)


class XbrlFact(UUIDPrimaryKey, Base):
    __tablename__ = "xbrl_facts"
    __table_args__ = (
        UniqueConstraint("filing_id", "concept", "context_id", "ordinal"),
        Index("ix_xbrl_facts_filing_concept", "filing_id", "concept"),
    )
    filing_id: Mapped[UUID] = mapped_column(ForeignKey("filings.id", ondelete="CASCADE"))
    concept: Mapped[str] = mapped_column(String(512))
    value_raw: Mapped[str] = mapped_column(Text)
    value_num: Mapped[Decimal | None] = mapped_column(Numeric(30, 8))
    unit: Mapped[str | None] = mapped_column(String(128))
    context_id: Mapped[str | None] = mapped_column(String(255))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    dimensions_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    ordinal: Mapped[int] = mapped_column(Integer)
    # Reported XBRL precision. Retained for provenance; it does not encode reporting scale.
    decimals: Mapped[int | None] = mapped_column(Integer)


class NseConceptMapping(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "nse_concept_mappings"
    __table_args__ = (
        UniqueConstraint("source_concept", "field_key"),
        CheckConstraint(
            "review_status IN ('provisional','needs_review','accepted','rejected')",
            name="review_status",
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence"),
    )
    source_concept: Mapped[str] = mapped_column(String(512), index=True)
    field_key: Mapped[str] = mapped_column(ForeignKey("field_defs.field_key"), index=True)
    target_unit: Mapped[str | None] = mapped_column(String(32))
    selection_strategy: Mapped[str] = mapped_column(String(64))
    unit_rules_json: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    rationale: Mapped[str] = mapped_column(Text)
    assumption: Mapped[str] = mapped_column(Text)
    evidence_url: Mapped[str] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(String(24), default="provisional", index=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text)
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FilingPage(UUIDPrimaryKey, Base):
    __tablename__ = "filing_pages"
    __table_args__ = (UniqueConstraint("filing_id", "page_no"),)
    filing_id: Mapped[UUID] = mapped_column(ForeignKey("filings.id", ondelete="CASCADE"))
    page_no: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    s3_image: Mapped[str | None] = mapped_column(Text)
    parse_version: Mapped[int] = mapped_column(Integer, default=1)
    section_key: Mapped[str | None] = mapped_column(String(64), index=True)
    locator_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    table_regions: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list)


class FieldDef(Base):
    __tablename__ = "field_defs"
    __table_args__ = (
        CheckConstraint("dtype IN ('text','number','integer','boolean','date')", name="dtype"),
    )
    field_key: Mapped[str] = mapped_column(String(160), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(32), index=True)
    principle: Mapped[str] = mapped_column(String(16), index=True)
    section: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(Text)
    dtype: Mapped[str] = mapped_column(String(16))
    unit_family: Mapped[str | None] = mapped_column(String(64))
    unit: Mapped[str | None] = mapped_column(String(32))
    core_kpi: Mapped[bool] = mapped_column(Boolean, default=False)
    xbrl_concept: Mapped[str | None] = mapped_column(String(255))


class ExtractedField(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "extracted_fields"
    __table_args__ = (
        UniqueConstraint("filing_id", "field_key", "version"),
        CheckConstraint("method IN ('xbrl','llm','human')", name="method"),
        CheckConstraint(
            "qa_status IN ('unreviewed','provisional','sampled_ok','corrected')",
            name="qa_status",
        ),
        CheckConstraint("qa_status = 'sampled_ok' OR confidence IS NOT NULL", name="qa_confidence"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="confidence"
        ),
        CheckConstraint("version > 0", name="positive_version"),
        UniqueConstraint("id", "filing_id", "field_key", name="uq_extracted_identity_scope"),
    )
    filing_id: Mapped[UUID] = mapped_column(ForeignKey("filings.id", ondelete="CASCADE"))
    field_key: Mapped[str] = mapped_column(ForeignKey("field_defs.field_key"))
    value_raw: Mapped[str] = mapped_column(Text)
    value_num: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    value_date: Mapped[date | None] = mapped_column(Date)
    unit: Mapped[str | None] = mapped_column(String(32))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    method: Mapped[str] = mapped_column(String(16))
    source_page: Mapped[int | None] = mapped_column(Integer)
    source_span: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    qa_status: Mapped[str] = mapped_column(String(24), default="unreviewed")
    version: Mapped[int] = mapped_column(Integer)


class FieldVersionPin(UUIDPrimaryKey, Base):
    __tablename__ = "field_version_pins"
    __table_args__ = (
        UniqueConstraint("filing_id", "field_key"),
        ForeignKeyConstraint(
            ["extracted_field_id", "filing_id", "field_key"],
            ["extracted_fields.id", "extracted_fields.filing_id", "extracted_fields.field_key"],
            name="fk_pins_extracted_identity_scope",
            ondelete="RESTRICT",
        ),
    )
    filing_id: Mapped[UUID] = mapped_column(ForeignKey("filings.id", ondelete="CASCADE"))
    field_key: Mapped[str] = mapped_column(ForeignKey("field_defs.field_key"))
    extracted_field_id: Mapped[UUID] = mapped_column(unique=True)
    pinned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    pinned_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))


class Metric(UUIDPrimaryKey, Base):
    __tablename__ = "metrics"
    __table_args__ = (UniqueConstraint("company_id", "fy", "metric_key"),)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    fy: Mapped[int] = mapped_column(Integer)
    metric_key: Mapped[str] = mapped_column(String(160))
    value: Mapped[Decimal] = mapped_column(Numeric(24, 6))
    percentile_sector: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    percentile_all: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    yoy_delta: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    field_version_pin_id: Mapped[UUID] = mapped_column(ForeignKey("field_version_pins.id"))
    # Every pin that contributed to `value`. A single-source metric repeats
    # `field_version_pin_id`; additive and multi-numerator metrics list all addends so the
    # lineage rule covers the whole number shown, not just its first component.
    contributing_pin_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)


class Score(UUIDPrimaryKey, Base):
    __tablename__ = "scores"
    __table_args__ = (UniqueConstraint("company_id", "fy", "score_key", "method_version"),)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    fy: Mapped[int] = mapped_column(Integer)
    score_key: Mapped[str] = mapped_column(String(160))
    value: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    components_json: Mapped[dict[str, object]] = mapped_column(JSONB)
    method_version: Mapped[str] = mapped_column(String(32))
    field_version_pin_id: Mapped[UUID] = mapped_column(ForeignKey("field_version_pins.id"))


class Embedding(UUIDPrimaryKey, Base):
    __tablename__ = "embeddings"
    __table_args__ = (
        CheckConstraint(
            "owner_kind IN ('filing_page','field_def','library_note')", name="owner_kind"
        ),
        UniqueConstraint("owner_kind", "owner_id", "model"),
        Index(
            "ix_embeddings_embedding_ivfflat",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
    owner_kind: Mapped[str] = mapped_column(String(32))
    owner_id: Mapped[UUID]
    embedding: Mapped[list[float]] = mapped_column(Vector(1024))
    model: Mapped[str] = mapped_column(String(100))


class LLMUsage(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "llm_usage"
    filing_id: Mapped[UUID] = mapped_column(ForeignKey("filings.id", ondelete="CASCADE"))
    prompt_key: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(32))
    call_count: Mapped[int] = mapped_column(Integer, default=1)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0)


class QAReview(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "qa_reviews"
    __table_args__ = (
        UniqueConstraint("extracted_field_id"),
        CheckConstraint("status IN ('queued','accepted','corrected')", name="status"),
    )
    extracted_field_id: Mapped[UUID] = mapped_column(
        ForeignKey("extracted_fields.id", ondelete="CASCADE")
    )
    family: Mapped[str] = mapped_column(String(64), index=True)
    confidence_band: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    reviewer_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    corrected_field_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("extracted_fields.id", ondelete="SET NULL")
    )


class QualityStat(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "quality_stats"
    __table_args__ = (UniqueConstraint("family"),)
    family: Mapped[str] = mapped_column(String(64), index=True)
    reviewed_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    accuracy: Mapped[Decimal] = mapped_column(Numeric(7, 6), default=0)


class SharedPhrase(UUIDPrimaryKey, Base):
    __tablename__ = "shared_phrases"
    __table_args__ = (UniqueConstraint("method_version", "phrase_hash"),)
    method_version: Mapped[str] = mapped_column(String(32))
    phrase_hash: Mapped[str] = mapped_column(String(64), index=True)
    phrase: Mapped[str] = mapped_column(Text)
    company_count: Mapped[int] = mapped_column(Integer)
