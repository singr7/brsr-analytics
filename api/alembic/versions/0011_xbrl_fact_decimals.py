"""Retain reported XBRL precision, and full pin lineage on multi-source metrics.

`decimals` is a precision claim, not a scale factor, so it cannot disambiguate the INR
reporting scale of a NSE BRSR filing. It is persisted for lossless provenance.

`contributing_pin_ids` lets an additive or multi-numerator metric carry every pin behind the
number shown, instead of anchoring lineage to its first component only.

Revision ID: 0011
Revises: 0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 0001 creates every table from the model metadata, so on a database built
    # from scratch these columns already exist. Guard them the way 0002-0004 do,
    # so the chain replays on an empty database as well as on an S01-era one.
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "decimals" not in {column["name"] for column in inspector.get_columns("xbrl_facts")}:
        op.add_column("xbrl_facts", sa.Column("decimals", sa.Integer(), nullable=True))

    if "contributing_pin_ids" not in {
        column["name"] for column in inspector.get_columns("metrics")
    }:
        op.add_column(
            "metrics",
            sa.Column(
                "contributing_pin_ids",
                postgresql.JSONB(),
                nullable=False,
                server_default="[]",
            ),
        )
        # Backfill only alongside the column that needs it: a database that
        # already has it has already been backfilled, or was never populated.
        op.execute(
            "UPDATE metrics SET contributing_pin_ids = "
            "jsonb_build_array(field_version_pin_id::text)"
        )


def downgrade() -> None:
    op.drop_column("metrics", "contributing_pin_ids")
    op.drop_column("xbrl_facts", "decimals")
