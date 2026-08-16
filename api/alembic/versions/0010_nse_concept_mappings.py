"""Add reviewable NSE-to-governed-field concept mappings.

Revision ID: 0010
Revises: 0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_extracted_fields_qa_status"), "extracted_fields", type_="check")
    op.create_check_constraint(
        "qa_status",
        "extracted_fields",
        "qa_status IN ('unreviewed','provisional','sampled_ok','corrected')",
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_field_version_pin() RETURNS trigger AS $$
        DECLARE
            candidate_status text;
            candidate_lineage jsonb;
        BEGIN
            SELECT qa_status, source_span INTO candidate_status, candidate_lineage
              FROM extracted_fields
             WHERE id = NEW.extracted_field_id;
            IF candidate_status NOT IN ('sampled_ok', 'corrected')
               AND NOT (
                   candidate_status = 'provisional'
                   AND candidate_lineage->>'source' = 'nse_brsr_xbrl'
                   AND candidate_lineage->>'mapping_id' IS NOT NULL
               ) THEN
                RAISE EXCEPTION 'only QA-passed or explicit provisional NSE fields may be pinned';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.create_table(
        "nse_concept_mappings",
        sa.Column("source_concept", sa.String(512), nullable=False),
        sa.Column("field_key", sa.String(160), nullable=False),
        sa.Column("target_unit", sa.String(32), nullable=True),
        sa.Column("selection_strategy", sa.String(64), nullable=False),
        sa.Column("unit_rules_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("assumption", sa.Text(), nullable=False),
        sa.Column("evidence_url", sa.Text(), nullable=False),
        sa.Column("review_status", sa.String(24), nullable=False, server_default="provisional"),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_nse_concept_mappings_confidence",
        ),
        sa.CheckConstraint(
            "review_status IN ('provisional','needs_review','accepted','rejected')",
            name="ck_nse_concept_mappings_review_status",
        ),
        sa.ForeignKeyConstraint(["field_key"], ["field_defs.field_key"]),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_concept", "field_key"),
    )
    op.create_index(
        "ix_nse_concept_mappings_source_concept", "nse_concept_mappings", ["source_concept"]
    )
    op.create_index("ix_nse_concept_mappings_field_key", "nse_concept_mappings", ["field_key"])
    op.create_index(
        "ix_nse_concept_mappings_review_status", "nse_concept_mappings", ["review_status"]
    )


def downgrade() -> None:
    op.drop_table("nse_concept_mappings")
    op.execute(
        "UPDATE extracted_fields SET qa_status = 'unreviewed' "
        "WHERE qa_status = 'provisional'"
    )
    op.drop_constraint(op.f("ck_extracted_fields_qa_status"), "extracted_fields", type_="check")
    op.create_check_constraint(
        "qa_status",
        "extracted_fields",
        "qa_status IN ('unreviewed','sampled_ok','corrected')",
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_field_version_pin() RETURNS trigger AS $$
        DECLARE
            candidate_status text;
        BEGIN
            SELECT qa_status INTO candidate_status
              FROM extracted_fields
             WHERE id = NEW.extracted_field_id;
            IF candidate_status NOT IN ('sampled_ok', 'corrected') THEN
                RAISE EXCEPTION 'only QA-passed extracted fields may be pinned';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
