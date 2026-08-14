"""Create the BRSR Lens relational spine.

Revision ID: 0001
Revises: None
"""

from collections.abc import Sequence

from alembic import op

from api.app.models import Base

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PIN_FUNCTION = """
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

PIN_TRIGGER = """
CREATE TRIGGER trg_validate_field_version_pin
BEFORE INSERT OR UPDATE ON field_version_pins
FOR EACH ROW EXECUTE FUNCTION validate_field_version_pin();
"""

EVENT_PARTITIONS = """
DO $$
DECLARE
    month_start date;
    partition_name text;
BEGIN
    FOR offset_month IN -12..24 LOOP
        month_start := (
            date_trunc('month', CURRENT_DATE)
            + (offset_month || ' months')::interval
        )::date;
        partition_name := 'events_' || to_char(month_start, 'YYYY_MM');
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF events FOR VALUES FROM (%L) TO (%L)',
            partition_name, month_start, month_start + interval '1 month'
        );
    END LOOP;
    CREATE TABLE IF NOT EXISTS events_default PARTITION OF events DEFAULT;
END $$;
"""


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    op.execute(PIN_FUNCTION)
    op.execute(PIN_TRIGGER)
    op.execute(EVENT_PARTITIONS)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS validate_field_version_pin() CASCADE")
    Base.metadata.drop_all(bind=op.get_bind())
