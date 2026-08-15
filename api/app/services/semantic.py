from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import Select, and_, asc, desc, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.models import Company, ExtractedField, FieldVersionPin, Filing, Metric, Score
from api.app.schemas.semantic import LineageRef, PolicyNotice, SemanticQuery

ROOT = Path(__file__).resolve().parents[3]
TIER_ORDER = {"explore": 0, "pro": 1, "studio": 2, "research": 3}


class SemanticError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SemanticCatalog:
    version: str
    minimum_cohort_size: int
    measures: dict[str, dict[str, Any]]
    dimensions: dict[str, dict[str, Any]]
    filters: dict[str, list[str]]
    shapes: tuple[str, ...]


def load_catalog(path: Path | None = None) -> SemanticCatalog:
    raw = yaml.safe_load((path or ROOT / "taxonomy" / "semantic.yaml").read_text())
    return SemanticCatalog(
        version=str(raw["version"]),
        minimum_cohort_size=int(raw["minimum_cohort_size"]),
        measures=dict(raw["measures"]),
        dimensions=dict(raw["dimensions"]),
        filters=dict(raw["filters"]),
        shapes=tuple(raw["shapes"]),
    )


def query_cache_key(query: SemanticQuery, tier: str) -> str:
    payload = query.model_dump(mode="json", exclude_none=True)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "semantic:v1:" + tier + ":" + hashlib.sha256(canonical.encode()).hexdigest()


def validate_query(query: SemanticQuery, tier: str, catalog: SemanticCatalog) -> list[PolicyNotice]:
    unknown_measures = set(query.measures) - set(catalog.measures)
    unknown_dimensions = set(query.dimensions) - set(catalog.dimensions)
    score_filter_keys = set(catalog.filters["score_band"])
    unknown_filter_dimensions = {
        item.dimension
        for item in query.filters
        if item.operator not in {"top_n", "bottom_n"}
    } - (set(catalog.dimensions) | score_filter_keys)
    if unknown_measures or unknown_dimensions or unknown_filter_dimensions:
        raise SemanticError(
            "Unknown catalog keys: "
            + ", ".join(sorted(unknown_measures | unknown_dimensions | unknown_filter_dimensions))
        )
    if query.shape not in catalog.shapes:
        raise SemanticError(f"Unsupported shape: {query.shape}")
    notices: list[PolicyNotice] = []
    for key in query.measures:
        allowed = catalog.measures[key].get("tiers", [])
        if tier not in allowed:
            notices.append(
                PolicyNotice(
                    code="tier_gated",
                    measure=key,
                    message=f"{key} requires one of: {', '.join(allowed)}",
                )
            )
    if "company" in query.dimensions and tier == "explore":
        notices.append(
            PolicyNotice(
                code="company_detail_gated",
                message="Company-level results require registration with a paid plan.",
            )
        )
    return notices


def _dimension_columns() -> dict[str, Any]:
    return {
        "sector": Company.sector,
        "industry": Company.industry,
        "mcap_band": Company.mcap_band,
        "fy": literal(None),  # replaced with the selected fact table's fy
        "company": Company.name,
        # Materialised assurance-readiness is the governed proxy at this phase.
        "assurance_status": literal("materialised"),
    }


def _filter_clauses(query: SemanticQuery, fact: type[Metric] | type[Score]) -> list[Any]:
    columns = _dimension_columns()
    columns["fy"] = fact.fy
    clauses: list[Any] = []
    for item in query.filters:
        value = item.value
        if item.operator in {"top_n", "bottom_n"}:
            continue
        column = fact.value if item.operator == "score_band" else columns[item.dimension]
        if item.operator == "eq":
            clauses.append(column == value)
        elif item.operator == "in":
            if not isinstance(value, list):
                raise SemanticError("in filters require a list value")
            clauses.append(column.in_(value))
        elif item.operator == "gte":
            clauses.append(column >= value)
        elif item.operator == "lte":
            clauses.append(column <= value)
        elif item.operator in {"between", "score_band"}:
            if not isinstance(value, list) or len(value) != 2:
                raise SemanticError(f"{item.operator} filters require [minimum, maximum]")
            clauses.append(column.between(value[0], value[1]))
    return clauses


def compile_measure_query(
    query: SemanticQuery, measure_key: str, catalog: SemanticCatalog
) -> Select[Any]:
    spec = catalog.measures[measure_key]
    fact: type[Metric] | type[Score] = Metric if spec["source"] == "metric" else Score
    key_column = Metric.metric_key if fact is Metric else Score.score_key
    dimensions = _dimension_columns()
    dimensions["fy"] = fact.fy
    selected = [dimensions[key].label(key) for key in query.dimensions]
    is_company_level = "company" in query.dimensions
    pin_column: Any
    if is_company_level or query.shape in {"single", "timeseries"}:
        value_column = fact.value.label("value")
        pin_column = fact.field_version_pin_id.label("pin_id")
        statement = select(*selected, value_column, pin_column)
    else:
        value_column = func.avg(fact.value).label("value")
        pin_column = literal(None).label("pin_id")
        statement = select(*selected, value_column, pin_column, func.count().label("cohort_n"))
    statement = statement.select_from(fact).join(Company, Company.id == fact.company_id)
    clauses = [key_column == measure_key, *_filter_clauses(query, fact)]
    if fact is Score:
        latest = select(func.max(Score.method_version)).scalar_subquery()
        clauses.append(Score.method_version == latest)
    statement = statement.where(and_(*clauses))
    if selected and not is_company_level and query.shape not in {"single", "timeseries"}:
        statement = statement.group_by(*[dimensions[key] for key in query.dimensions])
    ordering = (
        asc(value_column)
        if query.sort and query.sort.direction == "asc"
        else desc(value_column)
    )
    rank_filter = next(
        (item for item in query.filters if item.operator in {"top_n", "bottom_n"}), None
    )
    rank_limit = query.limit
    if rank_filter is not None:
        ordering = asc(value_column) if rank_filter.operator == "bottom_n" else desc(value_column)
        if isinstance(rank_filter.value, int):
            rank_limit = max(1, min(250, rank_filter.value))
    if query.shape == "timeseries":
        ordering = asc(fact.fy)
    return statement.order_by(ordering).limit(rank_limit)


async def source_refs(session: AsyncSession, pin_ids: set[str]) -> dict[str, list[LineageRef]]:
    if not pin_ids:
        return {}
    rows = (
        await session.execute(
            select(FieldVersionPin, ExtractedField, Filing)
            .join(ExtractedField, ExtractedField.id == FieldVersionPin.extracted_field_id)
            .join(Filing, Filing.id == FieldVersionPin.filing_id)
            .where(FieldVersionPin.id.in_(pin_ids))
        )
    ).all()
    return {
        str(pin.id): [
            LineageRef(
                pin_id=str(pin.id),
                filing_id=str(filing.id),
                field_key=field.field_key,
                source_page=field.source_page,
            )
        ]
        for pin, field, filing in rows
    }


async def execute_query(
    session: AsyncSession, query: SemanticQuery, tier: str, catalog: SemanticCatalog
) -> tuple[list[dict[str, object]], dict[str, list[LineageRef]], list[PolicyNotice]]:
    notices = validate_query(query, tier, catalog)
    gated = {notice.measure for notice in notices if notice.code == "tier_gated"}
    if any(notice.code == "company_detail_gated" for notice in notices):
        return [], {}, notices
    data: list[dict[str, object]] = []
    pins: set[str] = set()
    for measure in query.measures:
        if measure in gated:
            continue
        result = await session.execute(compile_measure_query(query, measure, catalog))
        for index, row in enumerate(result.mappings()):
            item = {key: value for key, value in row.items() if key != "pin_id"}
            item["measure"] = measure
            pin_id = row.get("pin_id")
            if pin_id is not None:
                pin = str(pin_id)
                pins.add(pin)
                item["cell_id"] = f"{measure}:{index}"
                item["lineage_key"] = pin
            cohort_n = row.get("cohort_n")
            if cohort_n is not None and int(cohort_n) < catalog.minimum_cohort_size:
                item["value"] = None
                notices.append(
                    PolicyNotice(
                        code="minimum_cohort",
                        measure=measure,
                        message=(
                            f"Suppressed cohort of {cohort_n}; minimum is "
                            f"{catalog.minimum_cohort_size}."
                        ),
                    )
                )
            data.append(item)
    # The critique-by-cohort rule is enforced after ordering and before serialization.
    bottom_requested = bool(query.sort and query.sort.direction == "asc") or any(
        item.operator == "bottom_n" for item in query.filters
    )
    if query.shape == "ranking" and bottom_requested:
        for item in data:
            item.pop("company", None)
            item["cohort"] = "anonymised lower-performing cohort"
        notices.append(
            PolicyNotice(
                code="bottom_ranking_anonymised",
                message="Lower-performing companies are reported only as an anonymised cohort.",
            )
        )
    return data, await source_refs(session, pins), notices
