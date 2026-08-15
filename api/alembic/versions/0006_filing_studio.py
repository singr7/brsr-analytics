"""Add Phase 3 Filing Studio state.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from api.app.models import Base

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column(
        "studio_filings",
        sa.Column("answers_revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "studio_docs",
        sa.Column("filename", sa.String(255), nullable=False, server_default="document"),
    )
    op.add_column(
        "studio_docs",
        sa.Column(
            "content_type",
            sa.String(100),
            nullable=False,
            server_default="application/octet-stream",
        ),
    )
    op.add_column(
        "studio_docs", sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("studio_answers", sa.Column("unit", sa.String(32), nullable=True))
    op.add_column("studio_answers", sa.Column("evidence_page", sa.Integer(), nullable=True))
    op.add_column("studio_answers", sa.Column("evidence_quote", sa.Text(), nullable=True))
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    for table in (
        "studio_token_usage",
        "studio_exports",
        "studio_editor_locks",
        "studio_comments",
        "studio_proposals",
    ):
        op.drop_table(table)
    for column in ("evidence_quote", "evidence_page", "unit"):
        op.drop_column("studio_answers", column)
    for column in ("size_bytes", "content_type", "filename"):
        op.drop_column("studio_docs", column)
    op.drop_column("studio_filings", "answers_revision")
