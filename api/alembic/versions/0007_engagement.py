"""Add Phase 4 engagement analytics and lead workflow state.

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from api.app.models import Base

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("analytics_opt_out", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("leads", sa.Column("outcome", sa.String(24), nullable=True))
    op.add_column("leads", sa.Column("outcome_note", sa.Text(), nullable=True))
    op.add_column(
        "leads", sa.Column("route_attempts", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("leads", sa.Column("route_error", sa.Text(), nullable=True))
    op.alter_column("deepdive_requests", "company_id", nullable=True)
    op.create_check_constraint(
        "ck_deepdive_requests_deepdive_status",
        "deepdive_requests",
        "status IN ('new','scoped','quoted','delivered')",
    )
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    op.drop_table("event_daily_aggregates")
    op.drop_constraint(
        "ck_deepdive_requests_deepdive_status", "deepdive_requests", type_="check"
    )
    op.alter_column("deepdive_requests", "company_id", nullable=False)
    for column in ("route_error", "route_attempts", "outcome_note", "outcome"):
        op.drop_column("leads", column)
    op.drop_column("users", "analytics_opt_out")
