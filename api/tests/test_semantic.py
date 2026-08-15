from sqlalchemy.dialects import postgresql

from api.app.schemas.semantic import SemanticQuery
from api.app.services.semantic import (
    compile_measure_query,
    load_catalog,
    query_cache_key,
    validate_query,
)


def test_catalog_query_compiles_user_values_as_bind_parameters() -> None:
    attack = "Energy'; DROP TABLE metrics; --"
    query = SemanticQuery.model_validate(
        {
            "measures": ["completeness"],
            "dimensions": ["sector"],
            "filters": [{"dimension": "sector", "operator": "eq", "value": attack}],
            "shape": "comparison",
        }
    )
    compiled = compile_measure_query(query, "completeness", load_catalog()).compile(
        dialect=postgresql.dialect()
    )
    assert attack not in str(compiled)
    assert attack in compiled.params.values()


def test_tier_and_bottom_ranking_policy_are_centralised() -> None:
    query = SemanticQuery.model_validate(
        {
            "measures": ["normalized.energy_gj_per_inr_crore"],
            "dimensions": ["company"],
            "shape": "ranking",
            "sort": {"direction": "asc"},
        }
    )
    notices = validate_query(query, "explore", load_catalog())
    assert {notice.code for notice in notices} == {"tier_gated", "company_detail_gated"}


def test_cache_key_is_stable_and_tier_scoped() -> None:
    query = SemanticQuery(measures=["substance"], dimensions=[], shape="single")
    assert query_cache_key(query, "pro") == query_cache_key(query, "pro")
    assert query_cache_key(query, "pro") != query_cache_key(query, "explore")
