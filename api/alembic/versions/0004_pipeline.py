"""Add parsing, extraction QA, usage, and corpus-scoring state.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from api.app.models import Base

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    filing_columns = {column["name"] for column in sa.inspect(bind).get_columns("filings")}
    filing_additions = {
        "parse_version": sa.Column(
            "parse_version", sa.Integer(), nullable=False, server_default="0"
        ),
        "parsed_pages": sa.Column("parsed_pages", sa.Integer(), nullable=False, server_default="0"),
        "sections_found": sa.Column(
            "sections_found", sa.Integer(), nullable=False, server_default="0"
        ),
        "xbrl_fact_count": sa.Column(
            "xbrl_fact_count", sa.Integer(), nullable=False, server_default="0"
        ),
        "section_confidence": sa.Column("section_confidence", sa.Numeric(5, 4)),
        "parsed_at": sa.Column("parsed_at", sa.DateTime(timezone=True)),
    }
    for name, column in filing_additions.items():
        if name not in filing_columns:
            op.add_column("filings", column)

    page_columns = {column["name"] for column in sa.inspect(bind).get_columns("filing_pages")}
    page_additions = {
        "parse_version": sa.Column(
            "parse_version", sa.Integer(), nullable=False, server_default="1"
        ),
        "section_key": sa.Column("section_key", sa.String(64)),
        "locator_confidence": sa.Column("locator_confidence", sa.Numeric(5, 4)),
        "table_regions": sa.Column("table_regions", sa.JSON(), nullable=False, server_default="[]"),
    }
    for name, column in page_additions.items():
        if name not in page_columns:
            op.add_column("filing_pages", column)
    page_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("filing_pages")}
    if "ix_filing_pages_section_key" not in page_indexes:
        op.create_index("ix_filing_pages_section_key", "filing_pages", ["section_key"])
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table in ("shared_phrases", "quality_stats", "qa_reviews", "llm_usage"):
        if inspector.has_table(table):
            op.drop_table(table)
    page_indexes = {index["name"] for index in inspector.get_indexes("filing_pages")}
    if "ix_filing_pages_section_key" in page_indexes:
        op.drop_index("ix_filing_pages_section_key", table_name="filing_pages")
    for name in ("table_regions", "locator_confidence", "section_key", "parse_version"):
        if name in {column["name"] for column in inspector.get_columns("filing_pages")}:
            op.drop_column("filing_pages", name)
    for name in (
        "parsed_at",
        "section_confidence",
        "xbrl_fact_count",
        "sections_found",
        "parsed_pages",
        "parse_version",
    ):
        if name in {column["name"] for column in inspector.get_columns("filings")}:
            op.drop_column("filings", name)
