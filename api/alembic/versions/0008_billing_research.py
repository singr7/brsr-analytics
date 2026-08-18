"""Add licence management, invoice requests and scoped Research API keys.

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from api.app.models import Base

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # See 0006: 0001 builds the full model schema, so these may already exist.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    additions = {
        "orgs": {
            "seat_limit": sa.Column("seat_limit", sa.Integer(), nullable=False, server_default="1"),
            "licence_starts_at": sa.Column(
                "licence_starts_at", sa.DateTime(timezone=True), nullable=True
            ),
            "licence_expires_at": sa.Column(
                "licence_expires_at", sa.DateTime(timezone=True), nullable=True
            ),
            "licence_grace_until": sa.Column(
                "licence_grace_until", sa.DateTime(timezone=True), nullable=True
            ),
        },
        "api_keys": {
            "scopes_json": sa.Column(
                "scopes_json",
                sa.dialects.postgresql.JSONB(),
                nullable=False,
                server_default="[]",
            ),
            "last_used_at": sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        },
    }
    for table, columns in additions.items():
        if not inspector.has_table(table):
            continue
        existing = {column["name"] for column in inspector.get_columns(table)}
        for name, column in columns.items():
            if name not in existing:
                op.add_column(table, column)
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    op.drop_table("invoice_requests")
    op.drop_column("api_keys", "last_used_at")
    op.drop_column("api_keys", "scopes_json")
    for name in ("licence_grace_until", "licence_expires_at", "licence_starts_at", "seat_limit"):
        op.drop_column("orgs", name)
