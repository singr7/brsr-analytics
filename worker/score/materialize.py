from __future__ import annotations

import hashlib
from collections import defaultdict
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.models import (
    Company,
    ExtractedField,
    FieldDef,
    FieldVersionPin,
    Filing,
    Metric,
    Score,
    SharedPhrase,
)
from worker.score.metrics import (
    MetricCandidate,
    assurance_readiness_score,
    completeness_score,
    load_scoring,
    materialize_percentiles,
    phrase_frequencies,
    substance_score,
)


def _id(kind: str, *parts: object) -> UUID:
    return uuid5(NAMESPACE_URL, "brsrlens/" + "/".join([kind, *map(str, parts)]))


async def rebuild_metrics(session: AsyncSession) -> tuple[int, int]:
    config = load_scoring()
    method_version = str(config["method_version"])
    definitions = list(await session.scalars(select(FieldDef)))
    all_fields = {definition.field_key for definition in definitions}
    core_fields = {definition.field_key for definition in definitions if definition.core_kpi}
    definition_by_key = {definition.field_key: definition for definition in definitions}
    rows = (
        await session.execute(
            select(Company, Filing, FieldVersionPin, ExtractedField)
            .join(Filing, Filing.company_id == Company.id)
            .join(FieldVersionPin, FieldVersionPin.filing_id == Filing.id)
            .join(ExtractedField, ExtractedField.id == FieldVersionPin.extracted_field_id)
            .order_by(Company.id, Filing.fy, FieldVersionPin.field_key)
        )
    ).all()
    by_filing: dict[UUID, list[tuple[Company, Filing, FieldVersionPin, ExtractedField]]] = (
        defaultdict(list)
    )
    for company, filing, pin, field in rows:
        by_filing[filing.id].append((company, filing, pin, field))

    candidates: list[MetricCandidate] = []
    for company, filing, pin, field in rows:
        if field.value_num is not None:
            candidates.append(
                MetricCandidate(
                    str(company.id),
                    filing.fy,
                    company.sector,
                    field.field_key,
                    field.value_num,
                    str(pin.id),
                )
            )
    for filing_rows in by_filing.values():
        company, filing, _, _ = filing_rows[0]
        values = {field.field_key: (field.value_num, pin.id) for _, _, pin, field in filing_rows}
        for derived in config["derived_metrics"]:
            numerator = values.get(str(derived["numerator"]))
            denominator = values.get(str(derived["denominator"]))
            if not numerator or not denominator or denominator[0] in {None, Decimal(0)}:
                continue
            numerator_value, numerator_pin = numerator
            denominator_value, _ = denominator
            if numerator_value is None or denominator_value is None:
                continue
            value = numerator_value / denominator_value * Decimal(str(derived["denominator_scale"]))
            candidates.append(
                MetricCandidate(
                    str(company.id),
                    filing.fy,
                    company.sector,
                    str(derived["metric_key"]),
                    value,
                    str(numerator_pin),
                )
            )

    await session.execute(delete(Metric))
    await session.execute(delete(Score).where(Score.method_version == method_version))
    await session.execute(delete(SharedPhrase).where(SharedPhrase.method_version == method_version))
    materialized = materialize_percentiles(
        candidates, minimum_sector_size=int(config["minimum_sector_size"])
    )
    for metric_row in materialized:
        item = metric_row.candidate
        session.add(
            Metric(
                id=_id("metric", item.company_id, item.fy, item.metric_key),
                company_id=UUID(item.company_id),
                fy=item.fy,
                metric_key=item.metric_key,
                value=item.value,
                percentile_sector=metric_row.percentile_sector,
                percentile_all=metric_row.percentile_all,
                yoy_delta=metric_row.yoy_delta,
                field_version_pin_id=UUID(item.pin_id),
            )
        )

    documents: dict[str, list[str]] = defaultdict(list)
    for company, _, _, field in rows:
        definition = definition_by_key[field.field_key]
        if definition.dtype == "text" and field.value_raw:
            documents[str(company.id)].append(field.value_raw)
    frequencies = phrase_frequencies(
        documents, phrase_words=int(config["substance"]["phrase_words"])
    )
    threshold = int(config["substance"]["boilerplate_company_threshold"])
    boilerplate = {digest for digest, (_, count) in frequencies.items() if count >= threshold}
    for digest in sorted(boilerplate):
        phrase, company_count = frequencies[digest]
        session.add(
            SharedPhrase(
                id=_id("phrase", method_version, digest),
                method_version=method_version,
                phrase_hash=digest,
                phrase=phrase,
                company_count=company_count,
            )
        )

    score_count = 0
    for filing_id in sorted(by_filing, key=str):
        filing_rows = by_filing[filing_id]
        company, filing, _, _ = filing_rows[0]
        fields = [field for _, _, _, field in filing_rows]
        pins = [pin for _, _, pin, _ in filing_rows]
        present = {field.field_key for field in fields}
        completeness, completeness_parts = completeness_score(
            present, core_fields, all_fields, config["completeness"]
        )
        texts = [
            field.value_raw
            for field in fields
            if definition_by_key[field.field_key].dtype == "text"
        ]
        substance, substance_parts = substance_score(texts, boilerplate, config["substance"])
        core_coverage = Decimal(len(present & core_fields)) / Decimal(max(1, len(core_fields)))
        lineage_count = sum(
            bool(field.source_page is not None and field.source_span)
            or bool(field.method == "xbrl" and field.source_span)
            for field in fields
        )
        lineage_quality = Decimal(lineage_count) / Decimal(max(1, len(fields)))
        assurance_present = any(
            ("assurance" in field.field_key or "assured" in field.field_key)
            and field.value_raw.strip().lower() not in {"", "false", "no", "nil"}
            for field in fields
        )
        assurance, assurance_parts = assurance_readiness_score(
            assurance_present, core_coverage, lineage_quality, config["assurance_readiness"]
        )
        anchor = min(pins, key=lambda pin: str(pin.id))
        for score_key, value, components in (
            ("completeness", completeness, completeness_parts),
            ("substance", substance, substance_parts),
            ("assurance_readiness", assurance, assurance_parts),
        ):
            session.add(
                Score(
                    id=_id("score", company.id, filing.fy, score_key, method_version),
                    company_id=company.id,
                    fy=filing.fy,
                    score_key=score_key,
                    value=value,
                    components_json={**components, "config_sha256": _config_hash()},
                    method_version=method_version,
                    field_version_pin_id=anchor.id,
                )
            )
            score_count += 1
    await session.commit()
    return len(materialized), score_count


def _config_hash() -> str:
    from worker.score.metrics import ROOT

    return hashlib.sha256((ROOT / "scoring.yaml").read_bytes()).hexdigest()
