from decimal import Decimal

import pytest

from api.app.models import ExtractedField
from api.app.services.llm import FakeLLM
from api.app.services.publication_policy import evaluate_publishability
from worker.extract.benchmark import benchmark
from worker.extract.contracts import ExtractionItem
from worker.extract.hygiene import check_total_relation, parse_numeric
from worker.extract.run import extract_batch
from worker.extract.validation import validate_extraction


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1,23,456", Decimal("123456")),
        ("2.5 crore", Decimal("25000000.0")),
        ("₹ 4 lakh", Decimal("400000")),
        ("Nil", Decimal(0)),
        ("12.5%", Decimal("12.5")),
        ("10 to 20", Decimal(15)),
    ],
)
def test_numeric_hygiene(raw: str, expected: Decimal) -> None:
    assert parse_numeric(raw).value == expected


def test_fabricated_quote_is_zeroed_and_flagged() -> None:
    item = ExtractionItem(
        field_key="p6.e1.energy_total_gj",
        value="9,999",
        source_page=12,
        source_quote="fabricated",
        confidence=0.99,
    )
    validated = validate_extraction(
        item,
        {12: "Total energy consumption was 1,000 GJ."},
        {"p6.e1.energy_total_gj"},
    )
    assert validated.confidence == 0
    assert validated.flags == ("source_quote_not_verbatim",)


async def test_fake_extraction_fixture_hits_golden_target() -> None:
    result = await benchmark()
    assert result == {"p6.e1": 1.0, "p6.e2": 1.0}


async def test_fabricated_fixture_trips_orchestrator_validation() -> None:
    result = await extract_batch(
        FakeLLM("fabricated_quote"),
        "environment",
        [{"field_key": "p6.e1.energy_total_gj"}],
        {12: "Total energy consumption was 1,000 GJ."},
    )
    assert result.fields[0].confidence == 0


def test_declared_relation_cross_check_downgrades_mismatch() -> None:
    result = check_total_relation(Decimal(100), [Decimal(40), Decimal(30)])
    assert result.passed is False
    assert result.flag == "declared_total_mismatch"


def test_publish_policy_requires_all_three_gates() -> None:
    field = ExtractedField(
        filing_id="00000000-0000-0000-0000-000000000001",
        field_key="p6.e1.energy_total_gj",
        value_raw="100",
        confidence=Decimal("0.95"),
        method="llm",
        qa_status="sampled_ok",
        version=1,
    )
    passed = evaluate_publishability(
        field,
        Decimal("0.99"),
        confidence_threshold=Decimal("0.9"),
        accuracy_target=Decimal("0.98"),
    )
    assert passed.allowed
    field.qa_status = "unreviewed"
    assert not evaluate_publishability(
        field,
        Decimal("0.99"),
        confidence_threshold=Decimal("0.9"),
        accuracy_target=Decimal("0.98"),
    ).allowed
