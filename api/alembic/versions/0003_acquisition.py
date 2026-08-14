"""Add governed acquisition provenance and resume cursors.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from api.app.models import Base

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    company_columns = {column["name"] for column in sa.inspect(bind).get_columns("companies")}
    if "ir_url" not in company_columns:
        op.add_column("companies", sa.Column("ir_url", sa.Text()))
    columns = {column["name"] for column in sa.inspect(bind).get_columns("filings")}
    additions = {
        "source_adapter": sa.Column("source_adapter", sa.String(64)),
        "source_url": sa.Column("source_url", sa.Text()),
        "filename": sa.Column("filename", sa.String(255)),
        "checksum_sha256": sa.Column("checksum_sha256", sa.String(64)),
        "acquisition_attempts": sa.Column(
            "acquisition_attempts", sa.Integer(), nullable=False, server_default="0"
        ),
        "acquisition_error": sa.Column("acquisition_error", sa.Text()),
    }
    for name, column in additions.items():
        if name not in columns:
            op.add_column("filings", column)
    index_names = {index["name"] for index in sa.inspect(bind).get_indexes("filings")}
    if "ix_filings_checksum_sha256" not in index_names:
        op.create_index("ix_filings_checksum_sha256", "filings", ["checksum_sha256"])
    op.alter_column(
        "filings", "acquired_at", existing_type=sa.DateTime(timezone=True), nullable=True
    )
    op.execute("UPDATE filings SET status = 'fetched' WHERE status = 'acquired'")
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("acquisition_cursors"):
        op.drop_table("acquisition_cursors")
    columns = {column["name"] for column in inspector.get_columns("filings")}
    index_names = {index["name"] for index in inspector.get_indexes("filings")}
    if "ix_filings_checksum_sha256" in index_names:
        op.drop_index("ix_filings_checksum_sha256", table_name="filings")
    for name in (
        "acquisition_error",
        "acquisition_attempts",
        "checksum_sha256",
        "filename",
        "source_url",
        "source_adapter",
    ):
        if name in columns:
            op.drop_column("filings", name)
    company_columns = {column["name"] for column in inspector.get_columns("companies")}
    if "ir_url" in company_columns:
        op.drop_column("companies", "ir_url")
