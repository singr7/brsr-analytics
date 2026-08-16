from decimal import Decimal
from pathlib import Path

from api.app.services.llm import FakeLLM
from worker.score.methodology import generate_methodology
from worker.score.metrics import (
    MetricCandidate,
    assurance_readiness_score,
    completeness_score,
    load_scoring,
    materialize_percentiles,
    phrase_frequencies,
    screen_implausible,
    substance_score,
)
from worker.score.substance import llm_substance_verdict


def test_hand_computed_percentiles_yoy_and_minimum_cohort_guard() -> None:
    rows = [
        MetricCandidate("a", 2024, "Energy", "emissions", Decimal(15), "pa0"),
        MetricCandidate("a", 2025, "Energy", "emissions", Decimal(10), "pa1"),
        MetricCandidate("b", 2025, "Energy", "emissions", Decimal(20), "pb1"),
        MetricCandidate("c", 2025, "Energy", "emissions", Decimal(30), "pc1"),
    ]
    first = materialize_percentiles(rows, minimum_sector_size=8)
    second = materialize_percentiles(rows, minimum_sector_size=8)
    assert first == second
    fy25 = [row for row in first if row.candidate.fy == 2025]
    assert [row.percentile_all for row in fy25] == [Decimal(0), Decimal(50), Decimal(100)]
    assert all(row.percentile_sector is None for row in fy25)
    assert fy25[0].yoy_delta == Decimal(-5)


def test_completeness_matches_hand_weighted_working() -> None:
    value, components = completeness_score(
        {"core.a", "essential.a"},
        {"core.a", "core.b"},
        {"core.a", "core.b", "essential.a", "essential.b"},
        {"core_weight": 2, "essential_weight": 1},
    )
    # (one core * 2 + one essential * 1) / (two cores * 2 + two essential * 1)
    assert value == Decimal(50)
    assert components["weighted_points"] == "3"


def test_cross_corpus_template_twins_are_boilerplate() -> None:
    template = (
        "We remain committed to sustainable development through responsible business practices"
    )
    documents = {"a": [template], "b": [template], "c": ["Entirely different disclosure"]}
    frequencies = phrase_frequencies(documents, phrase_words=8)
    boilerplate = {digest for digest, (_, count) in frequencies.items() if count >= 2}
    config = {
        "quantified_target_weight": 0.35,
        "dated_commitment_weight": 0.25,
        "named_methodology_weight": 0.20,
        "corpus_originality_weight": 0.20,
        "phrase_words": 8,
    }
    value, components = substance_score([template], boilerplate, config)
    assert value == Decimal(0)
    assert components["boilerplate_phrases"] == 3


def test_substance_and_assurance_components_are_explainable() -> None:
    config = load_scoring()
    text = "We commit to reduce emissions 30% by 2030 using the GHG Protocol."
    substance, components = substance_score([text], set(), config["substance"])
    assert substance == Decimal(100)
    assert components["quantified_target"] is True
    readiness, readiness_parts = assurance_readiness_score(
        True, Decimal("0.8"), Decimal("1"), config["assurance_readiness"]
    )
    assert readiness == Decimal(93)
    assert readiness_parts["lineage_quality"] == "1"


def test_methodology_document_is_generated_from_scoring_config() -> None:
    committed = Path("docs/methodology/substance_index.md").read_text(encoding="utf-8")
    assert committed == generate_methodology()


async def test_substance_llm_verdict_is_offline_fixture_backed() -> None:
    verdict = await llm_substance_verdict(
        FakeLLM(), "We will reduce emissions 30% by 2030 under the GHG Protocol."
    )
    assert verdict.quantified_target and verdict.dated_commitment
    assert verdict.named_methodology and verdict.confidence == 0.99


def _screen_config() -> dict[str, object]:
    return {
        "plausibility_screens": {
            "tolerance": 0.01,
            "identities": [{"total": "energy_total", "parts": ["renewable", "nonrenewable"]}],
            "non_negative": ["turnover"],
        },
        "additive_metrics": [],
        "derived_metrics": [
            {
                "metric_key": "energy_intensity",
                "numerator": "energy_total",
                "denominator": "turnover",
                "denominator_scale": 1,
            }
        ],
    }


def test_screen_keeps_metrics_whose_components_sum_to_their_total() -> None:
    rows = [
        MetricCandidate("a", 2025, "Energy", "energy_total", Decimal(100), "p1"),
        MetricCandidate("a", 2025, "Energy", "renewable", Decimal(40), "p2"),
        MetricCandidate("a", 2025, "Energy", "nonrenewable", Decimal(60), "p3"),
    ]
    kept, failures = screen_implausible(rows, _screen_config())
    assert failures == []
    assert len(kept) == 3


def test_screen_withholds_a_broken_identity_and_everything_derived_from_it() -> None:
    rows = [
        # A component reported at a different scale from its total breaks the identity.
        MetricCandidate("a", 2025, "Energy", "energy_total", Decimal(100), "p1"),
        MetricCandidate("a", 2025, "Energy", "renewable", Decimal(40000), "p2"),
        MetricCandidate("a", 2025, "Energy", "nonrenewable", Decimal(60), "p3"),
        MetricCandidate("a", 2025, "Energy", "turnover", Decimal(10), "p4"),
        MetricCandidate("a", 2025, "Energy", "energy_intensity", Decimal(10), "p1"),
        # A different filing stays untouched.
        MetricCandidate("b", 2025, "Energy", "energy_total", Decimal(100), "p5"),
        MetricCandidate("b", 2025, "Energy", "renewable", Decimal(40), "p6"),
        MetricCandidate("b", 2025, "Energy", "nonrenewable", Decimal(60), "p7"),
    ]
    kept, failures = screen_implausible(rows, _screen_config())
    assert [failure.metric_key for failure in failures] == ["energy_total"]
    withheld = {(row.company_id, row.metric_key) for row in rows} - {
        (row.company_id, row.metric_key) for row in kept
    }
    # The broken total and the intensity computed from it both go; company b is unaffected.
    assert withheld == {("a", "energy_total"), ("a", "energy_intensity")}


def test_screen_withholds_negative_values() -> None:
    rows = [MetricCandidate("a", 2025, "Energy", "turnover", Decimal(-5), "p1")]
    kept, failures = screen_implausible(rows, _screen_config())
    assert kept == []
    assert failures[0].screen == "non_negative"
