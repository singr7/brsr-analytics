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
    # See 0006: 0001 builds the full model schema, so these may already exist.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    additions = {
        "users": {
            "analytics_opt_out": sa.Column(
                "analytics_opt_out", sa.Boolean(), nullable=False, server_default=sa.false()
            ),
        },
        "leads": {
            "outcome": sa.Column("outcome", sa.String(24), nullable=True),
            "outcome_note": sa.Column("outcome_note", sa.Text(), nullable=True),
            "route_attempts": sa.Column(
                "route_attempts", sa.Integer(), nullable=False, server_default="0"
            ),
            "route_error": sa.Column("route_error", sa.Text(), nullable=True),
        },
    }
    for table, columns in additions.items():
        if not inspector.has_table(table):
            continue
        existing = {column["name"] for column in inspector.get_columns(table)}
        for name, column in columns.items():
            if name not in existing:
                op.add_column(table, column)

    if inspector.has_table("deepdive_requests"):
        op.alter_column("deepdive_requests", "company_id", nullable=True)
        constraints = {
            constraint["name"]
            for constraint in inspector.get_check_constraints("deepdive_requests")
        }
        if "ck_deepdive_requests_deepdive_status" not in constraints:
            # Bare name: the metadata naming convention adds the
            # ck_<table>_ prefix, and passing it in doubles it up.
            op.create_check_constraint(
                "deepdive_status",
                "deepdive_requests",
                "status IN ('new','scoped','quoted','delivered')",
            )
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    op.drop_table("event_daily_aggregates")
    op.drop_constraint(
        op.f("ck_deepdive_requests_deepdive_status"), "deepdive_requests", type_="check"
    )
    op.alter_column("deepdive_requests", "company_id", nullable=False)
    for column in ("route_error", "route_attempts", "outcome_note", "outcome"):
        op.drop_column("leads", column)
    op.drop_column("users", "analytics_opt_out")
