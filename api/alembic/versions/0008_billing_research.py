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
    op.add_column("orgs", sa.Column("seat_limit", sa.Integer(), nullable=False, server_default="1"))
    for name in ("licence_starts_at", "licence_expires_at", "licence_grace_until"):
        op.add_column("orgs", sa.Column(name, sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "api_keys",
        sa.Column(
            "scopes_json", sa.dialects.postgresql.JSONB(), nullable=False, server_default="[]"
        ),
    )
    op.add_column("api_keys", sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True))
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    op.drop_table("invoice_requests")
    op.drop_column("api_keys", "last_used_at")
    op.drop_column("api_keys", "scopes_json")
    for name in ("licence_grace_until", "licence_expires_at", "licence_starts_at", "seat_limit"):
        op.drop_column("orgs", name)
