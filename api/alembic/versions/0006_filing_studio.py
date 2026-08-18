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
    # 0001 creates every table from the model metadata, so on a database built
    # from scratch these columns already exist. Guard them the way 0002-0004 do,
    # so the chain replays on an empty database as well as on an S01-era one.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    additions = {
        "studio_filings": {
            "answers_revision": sa.Column(
                "answers_revision", sa.Integer(), nullable=False, server_default="0"
            ),
        },
        "studio_docs": {
            "filename": sa.Column(
                "filename", sa.String(255), nullable=False, server_default="document"
            ),
            "content_type": sa.Column(
                "content_type",
                sa.String(100),
                nullable=False,
                server_default="application/octet-stream",
            ),
            "size_bytes": sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        },
        "studio_answers": {
            "unit": sa.Column("unit", sa.String(32), nullable=True),
            "evidence_page": sa.Column("evidence_page", sa.Integer(), nullable=True),
            "evidence_quote": sa.Column("evidence_quote", sa.Text(), nullable=True),
        },
    }
    for table, columns in additions.items():
        # A table absent here is created complete by create_all below.
        if not inspector.has_table(table):
            continue
        existing = {column["name"] for column in inspector.get_columns(table)}
        for name, column in columns.items():
            if name not in existing:
                op.add_column(table, column)
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
