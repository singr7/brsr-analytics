"""Add production NSE ingestion inventory and lossless XBRL facts.

Revision ID: 0009
Revises: 0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("filings", sa.Column("submission_date", sa.Date(), nullable=True))
    op.add_column("filings", sa.Column("revision_date", sa.Date(), nullable=True))
    op.create_table(
        "ingestion_runs",
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("target_fy", sa.Integer(), nullable=False),
        sa.Column("batch_start", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requested_count", sa.Integer(), nullable=False),
        sa.Column("discovered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fetched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parsed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingestion_runs_source", "ingestion_runs", ["source"])
    op.create_index("ix_ingestion_runs_status", "ingestion_runs", ["status"])
    op.create_table(
        "ingestion_state",
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("next_offset", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("state_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("source"),
    )
    op.create_table(
        "xbrl_facts",
        sa.Column("filing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("concept", sa.String(512), nullable=False),
        sa.Column("value_raw", sa.Text(), nullable=False),
        sa.Column("value_num", sa.Numeric(30, 8), nullable=True),
        sa.Column("unit", sa.String(128), nullable=True),
        sa.Column("context_id", sa.String(255), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("dimensions_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["filing_id"], ["filings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("filing_id", "concept", "context_id", "ordinal"),
    )
    op.create_index("ix_xbrl_facts_filing_concept", "xbrl_facts", ["filing_id", "concept"])


def downgrade() -> None:
    op.drop_table("xbrl_facts")
    op.drop_table("ingestion_state")
    op.drop_table("ingestion_runs")
    op.drop_column("filings", "revision_date")
    op.drop_column("filings", "submission_date")
