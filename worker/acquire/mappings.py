from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

import yaml
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.models import (
    Company,
    ExtractedField,
    FieldVersionPin,
    Filing,
    NseConceptMapping,
    XbrlFact,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAPPING_PATH = ROOT / "taxonomy" / "nse_concept_mappings.yaml"


@dataclass(frozen=True, slots=True)
class MappingSpec:
    source_concept: str
    field_key: str
    target_unit: str | None
    selection_strategy: str
    unit_rules: dict[str, Decimal]
    value_strategy: str | None
    confidence: Decimal
    rationale: str
    assumption: str
    evidence_url: str


class UnresolvedUnitError(ValueError):
    """Raised when a fact's reported unit token has no declared conversion rule.

    Some issuers file a token that names no usable scale — FY25 has three filing energy
    totals under a bare `J` whose magnitudes are mutually inconsistent (one means GJ,
    another means millions of GJ). Like an unresolved turnover scale, this must withhold
    the single value rather than guess a factor or abort the whole publish pass.
    """


class UnresolvedScaleError(ValueError):
    """Raised when an issuer's reporting scale is not established by the reviewed registry.

    Callers must withhold the value rather than guess: publishing a plausible-looking but
    wrongly scaled turnover silently corrupts every intensity derived from it.
    """


@dataclass(frozen=True, slots=True)
class IssuerScale:
    scale: str
    confidence: Decimal
    evidence: str


@dataclass(frozen=True, slots=True)
class TurnoverScaleRegistry:
    absolute_threshold: Decimal
    factors: dict[str, Decimal]
    issuers: dict[str, IssuerScale]


@dataclass(frozen=True, slots=True)
class PublishResult:
    created: int
    pinned: int
    missing: int
    withheld: int


def _mapping_id(source_concept: str, field_key: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"brsrlens/nse-mapping/{source_concept}/{field_key}")


def load_turnover_scales(path: Path = DEFAULT_MAPPING_PATH) -> TurnoverScaleRegistry:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    block = document.get("turnover_scale") if isinstance(document, dict) else None
    if not isinstance(block, dict):
        raise ValueError("NSE concept mapping file requires a turnover_scale block")
    factors = {str(key): Decimal(str(value)) for key, value in block["factors"].items()}
    issuers: dict[str, IssuerScale] = {}
    for ticker, entry in (block.get("issuers") or {}).items():
        if not isinstance(entry, dict):
            raise ValueError(f"turnover_scale issuer {ticker} must be an object")
        scale = str(entry["scale"])
        if scale not in factors:
            raise ValueError(f"turnover_scale issuer {ticker} uses unknown scale {scale}")
        issuers[str(ticker).upper()] = IssuerScale(
            scale=scale,
            confidence=Decimal(str(entry["confidence"])),
            evidence=str(entry["evidence"]),
        )
    return TurnoverScaleRegistry(
        absolute_threshold=Decimal(str(block["absolute_threshold"])),
        factors=factors,
        issuers=issuers,
    )


def resolve_turnover_inr(
    value: Decimal, *, issuer: str | None, registry: TurnoverScaleRegistry
) -> tuple[Decimal, str]:
    """Return turnover in absolute INR plus the scale token that produced it."""
    if value >= registry.absolute_threshold:
        return value, "absolute"
    entry = registry.issuers.get((issuer or "").upper())
    if entry is None:
        raise UnresolvedScaleError(
            f"turnover scale for issuer {issuer or '(unknown)'} is not in the reviewed registry"
        )
    return value * registry.factors[entry.scale], entry.scale


def load_mapping_specs(path: Path = DEFAULT_MAPPING_PATH) -> tuple[str, list[MappingSpec]]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("mappings"), list):
        raise ValueError("NSE concept mapping file requires a mappings list")
    version = str(document["version"])
    evidence_url = str(document["evidence_url"])
    default_selection = str(document["selection_strategy"])
    specs: list[MappingSpec] = []
    for row in document["mappings"]:
        if not isinstance(row, dict):
            raise ValueError("Each NSE concept mapping must be an object")
        rules = row.get("unit_rules", {})
        if not isinstance(rules, dict):
            raise ValueError("unit_rules must be an object")
        specs.append(
            MappingSpec(
                source_concept=str(row["source_concept"]),
                field_key=str(row["field_key"]),
                target_unit=str(row["target_unit"]) if row.get("target_unit") else None,
                selection_strategy=str(row.get("selection_strategy", default_selection)),
                unit_rules={str(key): Decimal(str(value)) for key, value in rules.items()},
                value_strategy=str(row["value_strategy"]) if row.get("value_strategy") else None,
                confidence=Decimal(str(row["confidence"])),
                rationale=str(row["rationale"]),
                assumption=str(row["assumption"]),
                evidence_url=evidence_url,
            )
        )
    return version, specs


async def seed_concept_mappings(
    session: AsyncSession, specs: list[MappingSpec]
) -> list[NseConceptMapping]:
    rows: list[NseConceptMapping] = []
    for spec in specs:
        mapping = await session.scalar(
            select(NseConceptMapping).where(
                NseConceptMapping.source_concept == spec.source_concept,
                NseConceptMapping.field_key == spec.field_key,
            )
        )
        rules: dict[str, object] = {key: str(value) for key, value in spec.unit_rules.items()}
        if spec.value_strategy:
            rules["__value_strategy"] = spec.value_strategy
        if mapping is None:
            mapping = NseConceptMapping(
                id=_mapping_id(spec.source_concept, spec.field_key),
                source_concept=spec.source_concept,
                field_key=spec.field_key,
                review_status="provisional",
            )
        mapping.target_unit = spec.target_unit
        mapping.selection_strategy = spec.selection_strategy
        mapping.unit_rules_json = rules
        mapping.confidence = spec.confidence
        mapping.rationale = spec.rationale
        mapping.assumption = spec.assumption
        mapping.evidence_url = spec.evidence_url
        session.add(mapping)
        rows.append(mapping)
    await session.commit()
    return rows


def convert_numeric_value(
    value: Decimal | None,
    unit: str | None,
    rules: dict[str, object],
    *,
    issuer: str | None = None,
    registry: TurnoverScaleRegistry | None = None,
) -> tuple[Decimal, str] | None:
    """Return the converted value and the scale token recorded in lineage."""
    if value is None:
        return None
    if rules.get("__value_strategy") == "registered_turnover_scale":
        if registry is None:
            raise UnresolvedScaleError("a turnover scale registry is required")
        return resolve_turnover_inr(value, issuer=issuer, registry=registry)
    factor = rules.get(unit or "")
    if factor is None:
        raise UnresolvedUnitError(f"No conversion for unit {unit or '(none)'}")
    return value * Decimal(str(factor)), unit or ""


def _converted_value(
    fact: XbrlFact,
    mapping: NseConceptMapping,
    *,
    issuer: str | None,
    registry: TurnoverScaleRegistry,
) -> tuple[Decimal, str] | None:
    try:
        return convert_numeric_value(
            fact.value_num, fact.unit, mapping.unit_rules_json, issuer=issuer, registry=registry
        )
    except (UnresolvedScaleError, UnresolvedUnitError):
        raise
    except ValueError as exc:
        raise ValueError(f"{mapping.source_concept}: {exc}") from exc


async def publish_provisional_mappings(
    session: AsyncSession,
    *,
    target_fy: int,
    path: Path = DEFAULT_MAPPING_PATH,
) -> PublishResult:
    mapping_version, specs = load_mapping_specs(path)
    scales = load_turnover_scales(path)
    mappings = await seed_concept_mappings(session, specs)
    active = [mapping for mapping in mappings if mapping.review_status != "rejected"]
    rejected_keys = {
        mapping.field_key for mapping in mappings if mapping.review_status == "rejected"
    }
    if rejected_keys:
        nse_filing_ids = select(Filing.id).where(
            Filing.source_adapter == "nse_brsr", Filing.fy == target_fy
        )
        await session.execute(
            delete(FieldVersionPin).where(
                FieldVersionPin.filing_id.in_(nse_filing_ids),
                FieldVersionPin.field_key.in_(rejected_keys),
            )
        )
        await session.commit()
    concepts = {mapping.source_concept for mapping in active}
    rows = (
        await session.execute(
            select(Filing, XbrlFact)
            .join(XbrlFact, XbrlFact.filing_id == Filing.id)
            .where(
                Filing.source_adapter == "nse_brsr",
                Filing.fy == target_fy,
                XbrlFact.concept.in_(concepts),
                XbrlFact.period_end == date(target_fy, 3, 31),
                XbrlFact.context_id == "DCYMain",
            )
            .order_by(Filing.id, XbrlFact.ordinal)
        )
    ).all()
    facts = {(filing.id, fact.concept): fact for filing, fact in rows}
    created = 0
    pinned = 0
    missing = 0
    withheld = 0
    filing_rows = (
        await session.execute(
            select(Filing, Company)
            .join(Company, Company.id == Filing.company_id)
            .where(Filing.source_adapter == "nse_brsr", Filing.fy == target_fy)
        )
    ).all()
    for filing, company in filing_rows:
        for mapping in active:
            fact = facts.get((filing.id, mapping.source_concept))
            if fact is None:
                missing += 1
                continue
            try:
                resolved = _converted_value(
                    fact, mapping, issuer=company.ticker, registry=scales
                )
            except (UnresolvedScaleError, UnresolvedUnitError):
                # Fail closed: withhold the value and drop any pin from an earlier run so a
                # previously guessed number cannot keep serving. One unresolvable fact
                # withholds only itself; the rest of the cohort still publishes.
                await session.execute(
                    delete(FieldVersionPin).where(
                        FieldVersionPin.filing_id == filing.id,
                        FieldVersionPin.field_key == mapping.field_key,
                    )
                )
                withheld += 1
                continue
            if resolved is None:
                missing += 1
                continue
            converted, scale_token = resolved
            latest = await session.scalar(
                select(ExtractedField)
                .where(
                    ExtractedField.filing_id == filing.id,
                    ExtractedField.field_key == mapping.field_key,
                )
                .order_by(ExtractedField.version.desc())
                .limit(1)
            )
            lineage: dict[str, object] = {
                "source": "nse_brsr_xbrl",
                "source_fact_id": str(fact.id),
                "source_concept": fact.concept,
                "context_id": fact.context_id,
                "period_start": fact.period_start.isoformat() if fact.period_start else None,
                "period_end": fact.period_end.isoformat() if fact.period_end else None,
                "reported_unit": fact.unit,
                "target_unit": mapping.target_unit,
                "mapping_id": str(mapping.id),
                "mapping_version": mapping_version,
                "review_status": mapping.review_status,
                "conversion_rules": mapping.unit_rules_json,
                "reported_decimals": fact.decimals,
                "resolved_scale": scale_token,
            }
            reusable = bool(
                latest
                and latest.source_span
                and latest.source_span.get("source_fact_id") == str(fact.id)
                and latest.source_span.get("mapping_version") == mapping_version
            )
            if reusable and latest is not None:
                field = latest
            else:
                version = int(
                    await session.scalar(
                        select(func.coalesce(func.max(ExtractedField.version), 0)).where(
                            ExtractedField.filing_id == filing.id,
                            ExtractedField.field_key == mapping.field_key,
                        )
                    )
                    or 0
                ) + 1
                field = ExtractedField(
                    filing_id=filing.id,
                    field_key=mapping.field_key,
                    value_raw=fact.value_raw,
                    value_num=converted,
                    unit=mapping.target_unit,
                    confidence=mapping.confidence,
                    method="xbrl",
                    source_page=None,
                    source_span=lineage,
                    qa_status="provisional",
                    version=version,
                )
                session.add(field)
                await session.flush()
                created += 1
            pin = await session.scalar(
                select(FieldVersionPin).where(
                    FieldVersionPin.filing_id == filing.id,
                    FieldVersionPin.field_key == mapping.field_key,
                )
            )
            if pin is None:
                pin = FieldVersionPin(
                    filing_id=filing.id,
                    field_key=mapping.field_key,
                    extracted_field_id=field.id,
                )
            else:
                pin.extracted_field_id = field.id
            session.add(pin)
            pinned += 1
    await session.commit()
    return PublishResult(
        created=created, pinned=pinned, missing=missing, withheld=withheld
    )
