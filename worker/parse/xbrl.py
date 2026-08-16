from __future__ import annotations

import contextlib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree

from api.app.services.units import convert_unit


@dataclass(frozen=True, slots=True)
class XbrlField:
    field_key: str
    value_raw: str
    value_num: Decimal | None
    unit: str | None
    period_start: date | None
    period_end: date | None
    decimals: int | None
    context_id: str | None


@dataclass(frozen=True, slots=True)
class RawXbrlFact:
    concept: str
    value_raw: str
    value_num: Decimal | None
    unit: str | None
    period_start: date | None
    period_end: date | None
    context_id: str | None
    dimensions: dict[str, str]
    ordinal: int


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":")[-1]


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def parse_xbrl(
    content: bytes,
    concept_mapping: dict[str, tuple[str, str | None]],
) -> list[XbrlField]:
    """Parse an instance document into mapped facts.

    The representation is intentionally independent of Arelle. Production deployments may
    validate and load the instance with Arelle first; this strict XML path keeps CI and
    synthetic fixtures offline while preserving contexts, units and decimals.
    """
    root = ElementTree.fromstring(content)
    contexts: dict[str, tuple[date | None, date | None]] = {}
    units: dict[str, str] = {}
    for element in root.iter():
        name = _local_name(element.tag)
        element_id = element.attrib.get("id")
        if name == "context" and element_id:
            start = next(
                (child.text for child in element.iter() if _local_name(child.tag) == "startDate"),
                None,
            )
            end = next(
                (
                    child.text
                    for child in element.iter()
                    if _local_name(child.tag) in {"endDate", "instant"}
                ),
                None,
            )
            contexts[element_id] = (_parse_date(start), _parse_date(end))
        elif name == "unit" and element_id:
            measure = next(
                (child.text for child in element.iter() if _local_name(child.tag) == "measure"),
                None,
            )
            if measure:
                units[element_id] = measure.split(":")[-1]

    output: list[XbrlField] = []
    for element in root.iter():
        concept = _local_name(element.tag)
        mapped = concept_mapping.get(concept)
        raw = (element.text or "").strip()
        if mapped is None or not raw:
            continue
        field_key, expected_unit = mapped
        unit = units.get(element.attrib.get("unitRef", ""), expected_unit)
        number: Decimal | None = None
        with contextlib.suppress(InvalidOperation):
            number = Decimal(raw.replace(",", ""))
        if number is not None and unit:
            # Taxonomy-specific units remain raw for downstream QA.
            with contextlib.suppress(ValueError):
                number, unit = convert_unit(number, unit, expected_unit)
        context_id = element.attrib.get("contextRef")
        period = contexts.get(context_id or "", (None, None))
        decimals_raw = element.attrib.get("decimals")
        decimals = (
            int(decimals_raw) if decimals_raw and decimals_raw.lstrip("-").isdigit() else None
        )
        output.append(
            XbrlField(field_key, raw, number, unit, period[0], period[1], decimals, context_id)
        )
    return output


def parse_raw_xbrl_facts(content: bytes) -> list[RawXbrlFact]:
    """Return every reported XBRL fact without depending on a local taxonomy mapping."""
    root = ElementTree.fromstring(content)
    contexts: dict[str, tuple[date | None, date | None, dict[str, str]]] = {}
    units: dict[str, str] = {}
    for element in root.iter():
        name = _local_name(element.tag)
        element_id = element.attrib.get("id")
        if name == "context" and element_id:
            start = next(
                (child.text for child in element.iter() if _local_name(child.tag) == "startDate"),
                None,
            )
            end = next(
                (
                    child.text
                    for child in element.iter()
                    if _local_name(child.tag) in {"endDate", "instant"}
                ),
                None,
            )
            dimensions = {
                child.attrib.get("dimension", _local_name(child.tag)): (child.text or "").strip()
                for child in element.iter()
                if _local_name(child.tag) in {"explicitMember", "typedMember"}
            }
            contexts[element_id] = (_parse_date(start), _parse_date(end), dimensions)
        elif name == "unit" and element_id:
            measures = [
                (child.text or "").split(":")[-1]
                for child in element.iter()
                if _local_name(child.tag) == "measure" and child.text
            ]
            if measures:
                units[element_id] = "/".join(measures)

    facts: list[RawXbrlFact] = []
    for ordinal, element in enumerate(root.iter()):
        context_id = element.attrib.get("contextRef")
        raw = (element.text or "").strip()
        if not context_id or not raw or list(element):
            continue
        number: Decimal | None = None
        with contextlib.suppress(InvalidOperation):
            number = Decimal(raw.replace(",", ""))
        period_start, period_end, dimensions = contexts.get(
            context_id, (None, None, {})
        )
        facts.append(
            RawXbrlFact(
                concept=_local_name(element.tag),
                value_raw=raw,
                value_num=number,
                unit=units.get(element.attrib.get("unitRef", "")),
                period_start=period_start,
                period_end=period_end,
                context_id=context_id,
                dimensions=dimensions,
                ordinal=ordinal,
            )
        )
    return facts
