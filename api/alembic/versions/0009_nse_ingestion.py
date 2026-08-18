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
    # 0001 creates every table from the model metadata, so on a database built
    # from scratch these objects already exist. Guard them the way 0002-0004 do,
    # so the chain replays on an empty database as well as on an S01-era one.
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    filing_columns = {column["name"] for column in inspector.get_columns("filings")}
    filing_additions = {
        "submission_date": sa.Column("submission_date", sa.Date(), nullable=True),
        "revision_date": sa.Column("revision_date", sa.Date(), nullable=True),
    }
    for name, column in filing_additions.items():
        if name not in filing_columns:
            op.add_column("filings", column)

    if not inspector.has_table("ingestion_runs"):
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
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    if not inspector.has_table("ingestion_state"):
        op.create_table(
            "ingestion_state",
            sa.Column("source", sa.String(64), nullable=False),
            sa.Column("next_offset", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("state_json", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("source"),
        )
    if not inspector.has_table("xbrl_facts"):
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
    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("ingestion_runs")}
    if "ix_ingestion_runs_source" not in indexes:
        op.create_index("ix_ingestion_runs_source", "ingestion_runs", ["source"])
    if "ix_ingestion_runs_status" not in indexes:
        op.create_index("ix_ingestion_runs_status", "ingestion_runs", ["status"])
    indexes = {index["name"] for index in inspector.get_indexes("xbrl_facts")}
    if "ix_xbrl_facts_filing_concept" not in indexes:
        op.create_index("ix_xbrl_facts_filing_concept", "xbrl_facts", ["filing_id", "concept"])


def downgrade() -> None:
    op.drop_table("xbrl_facts")
    op.drop_table("ingestion_state")
    op.drop_table("ingestion_runs")
    op.drop_column("filings", "revision_date")
    op.drop_column("filings", "submission_date")
