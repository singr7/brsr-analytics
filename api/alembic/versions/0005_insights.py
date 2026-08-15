"""Add Phase 2 trust and learning-library state.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

from alembic import op

from api.app.models import Base

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    for table in (
        "company_annotations",
        "library_exemplars",
        "library_patterns",
        "correction_tickets",
    ):
        op.drop_table(table)
