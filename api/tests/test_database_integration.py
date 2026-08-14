import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from api.app.db.session import create_engine

pytestmark = pytest.mark.skipif(
    os.getenv("BRSRLENS_DB_TESTS") != "true",
    reason="set BRSRLENS_DB_TESTS=true against a migrated fixture database",
)


async def test_seed_is_complete_and_unreviewed_version_is_not_pinned() -> None:
    engine = create_engine()
    async with engine.connect() as connection:
        companies = await connection.scalar(text("SELECT count(*) FROM companies"))
        filings = await connection.scalar(text("SELECT count(*) FROM filings"))
        field_defs = await connection.scalar(text("SELECT count(*) FROM field_defs"))
        mismatches = await connection.scalar(
            text("""
            SELECT count(*) FROM field_version_pins p
            JOIN extracted_fields e ON e.id = p.extracted_field_id
            WHERE e.qa_status NOT IN ('sampled_ok', 'corrected')
               OR e.filing_id <> p.filing_id OR e.field_key <> p.field_key
        """)
        )
        unreviewed_v2_pinned = await connection.scalar(
            text("""
            SELECT count(*) FROM extracted_fields e
            JOIN field_version_pins p ON p.extracted_field_id = e.id
            WHERE e.version = 2 AND e.qa_status = 'unreviewed'
        """)
        )
    await engine.dispose()
    assert (companies, filings, field_defs) == (20, 40, 120)
    assert mismatches == 0
    assert unreviewed_v2_pinned == 0


async def test_current_event_routes_to_monthly_partition() -> None:
    engine = create_engine()
    event_id = uuid4()
    occurred_at = datetime.now(UTC)
    async with engine.begin() as connection:
        await connection.execute(
            text("""
                INSERT INTO events (id, session_id, name, props_json, ts)
                VALUES (:id, :session_id, 'session_started', '{}'::jsonb, :ts)
            """),
            {"id": event_id, "session_id": uuid4(), "ts": occurred_at},
        )
        partition = await connection.scalar(
            text("SELECT tableoid::regclass::text FROM events WHERE id = :id AND ts = :ts"),
            {"id": event_id, "ts": occurred_at},
        )
        await connection.execute(
            text("DELETE FROM events WHERE id = :id AND ts = :ts"),
            {"id": event_id, "ts": occurred_at},
        )
    await engine.dispose()
    assert partition == f"events_{occurred_at:%Y_%m}"


async def test_database_rejects_pin_to_unreviewed_version() -> None:
    engine = create_engine()
    async with engine.connect() as connection:
        transaction = await connection.begin()
        candidate = (
            await connection.execute(
                text("""
                    SELECT p.id AS pin_id, candidate.id AS candidate_id
                    FROM field_version_pins p
                    JOIN extracted_fields published ON published.id = p.extracted_field_id
                    JOIN extracted_fields candidate
                      ON candidate.filing_id = published.filing_id
                     AND candidate.field_key = published.field_key
                    WHERE candidate.version = 2 AND candidate.qa_status = 'unreviewed'
                    LIMIT 1
                """)
            )
        ).mappings().one()
        with pytest.raises(DBAPIError, match="only QA-passed extracted fields may be pinned"):
            await connection.execute(
                text("""
                    UPDATE field_version_pins SET extracted_field_id = :candidate_id
                    WHERE id = :pin_id
                """),
                candidate,
            )
        await transaction.rollback()
    await engine.dispose()
