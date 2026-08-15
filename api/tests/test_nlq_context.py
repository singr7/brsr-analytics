from api.app.schemas.semantic import SemanticQuery
from api.app.services.nlq import merge_context
from api.app.services.semantic import load_catalog, validate_query


def query(*, fy: int, sector: str | None = None) -> SemanticQuery:
    filters: list[dict[str, object]] = [{"dimension": "fy", "operator": "eq", "value": fy}]
    if sector:
        filters.append({"dimension": "sector", "operator": "eq", "value": sector})
    return SemanticQuery.model_validate(
        {
            "measures": ["completeness"],
            "dimensions": ["sector"],
            "filters": filters,
            "shape": "comparison",
        }
    )


def test_followup_inherits_visible_filters_and_overrides_conflicts() -> None:
    merged, provenance = merge_context(query(fy=2025, sector="Energy"), query(fy=2024))
    values = {item.dimension: item.value for item in merged.filters}
    assert values == {"sector": "Energy", "fy": 2024}
    assert provenance.inherited_filters == ["sector"]
    assert provenance.overridden_filters == ["fy"]


def test_merged_context_still_uses_central_tier_policy() -> None:
    base = query(fy=2025, sector="Energy")
    translated = SemanticQuery.model_validate(
        {
            "measures": ["normalized.energy_gj_per_inr_crore"],
            "dimensions": ["company"],
            "shape": "ranking",
        }
    )
    merged, _ = merge_context(base, translated)
    notices = validate_query(merged, "explore", load_catalog())
    assert {notice.code for notice in notices} == {"tier_gated", "company_detail_gated"}
