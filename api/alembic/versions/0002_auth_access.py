"""Add authentication lifecycle and organisation invite state.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from api.app.models import Base

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Models are the schema source in this early phase; checkfirst keeps upgrades safe
    # for databases created by the S01/S02 metadata-based initial migration.
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("users")}
    if "is_admin" not in columns:
        op.add_column(
            "users", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false")
        )
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table in ("org_invites", "email_verifications", "refresh_tokens"):
        if inspector.has_table(table):
            op.drop_table(table)
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "is_admin" in columns:
        op.drop_column("users", "is_admin")
