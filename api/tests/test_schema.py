from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from api.app.db.taxonomy import FIELD_KEY_PATTERN, load_form_schema
from api.app.models import Base
from api.app.services.publication import ExtractionVersion, latest_publishable


def test_relational_spine_is_complete() -> None:
    expected = {
        "companies",
        "acquisition_cursors",
        "filings",
        "filing_pages",
        "field_defs",
        "extracted_fields",
        "field_version_pins",
        "metrics",
        "scores",
        "embeddings",
        "llm_usage",
        "qa_reviews",
        "quality_stats",
        "shared_phrases",
        "users",
        "orgs",
        "memberships",
        "plans",
        "api_keys",
        "refresh_tokens",
        "email_verifications",
        "org_invites",
        "events",
        "event_daily_aggregates",
        "leads",
        "deepdive_requests",
        "studio_orgs",
        "studio_filings",
        "studio_answers",
        "studio_docs",
        "studio_proposals",
        "studio_comments",
        "studio_editor_locks",
        "studio_exports",
        "studio_token_usage",
        "correction_tickets",
        "library_patterns",
        "library_exemplars",
        "company_annotations",
    }
    assert set(Base.metadata.tables) == expected


def test_form_schema_contains_complete_phase3_format() -> None:
    version, fields = load_form_schema()
    keys = {field["field_key"] for field in fields}
    assert version == "1.0.0"
    assert len(fields) == len(keys) == 300
    assert all(FIELD_KEY_PATTERN.fullmatch(key) for key in keys)
    assert {
        "a.basics.company_name",
        "p3.workforce.employees_permanent_female",
        "p5.human_rights.complaints_sexual_harassment",
        "p6.e1.energy_total_gj",
        "p6.e2.water_total_kl",
        "p6.e3.scope1_tco2e",
        "p6.e5.waste_recycled_mt",
        "b.policy.p9.external_assessment",
        "p8.leadership.outcome",
    } <= keys


def test_form_schema_path_is_repo_relative() -> None:
    _, fields = load_form_schema(Path("taxonomy/form_schema.yaml"))
    assert fields


@given(
    passed_version=st.integers(min_value=1, max_value=1_000),
    extra_unreviewed=st.lists(st.integers(min_value=1_001, max_value=10_000), max_size=20),
)
def test_unreviewed_versions_never_change_public_value(
    passed_version: int, extra_unreviewed: list[int]
) -> None:
    versions = [ExtractionVersion(passed_version, "sampled_ok")]
    before = latest_publishable(versions)
    after = latest_publishable(
        versions + [ExtractionVersion(version, "unreviewed") for version in extra_unreviewed]
    )
    assert after == before
