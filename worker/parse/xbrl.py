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
