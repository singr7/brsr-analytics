from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from api.app.models.base import Base, Timestamped, UUIDPrimaryKey


class CorrectionTicket(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "correction_tickets"
    __table_args__ = (
        CheckConstraint("status IN ('open','triaged','resolved','rejected')", name="status"),
    )
    field_version_pin_id: Mapped[UUID] = mapped_column(ForeignKey("field_version_pins.id"))
    reporter_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open")


class LibraryPattern(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "library_patterns"
    title: Mapped[str] = mapped_column(String(200))
    pattern_note: Mapped[str] = mapped_column(Text)
    topic: Mapped[str] = mapped_column(String(100), index=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)


class LibraryExemplar(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "library_exemplars"
    pattern_id: Mapped[UUID] = mapped_column(
        ForeignKey("library_patterns.id", ondelete="CASCADE")
    )
    filing_page_id: Mapped[UUID] = mapped_column(ForeignKey("filing_pages.id"))
    excerpt: Mapped[str] = mapped_column(Text)
    company_permission: Mapped[bool] = mapped_column(Boolean, default=False)


class CompanyAnnotation(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "company_annotations"
    __table_args__ = (
        CheckConstraint("status IN ('published','withdrawn')", name="status"),
    )
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    field_version_pin_id: Mapped[UUID] = mapped_column(ForeignKey("field_version_pins.id"))
    author_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="published")
