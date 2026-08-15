from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from api.app.db.taxonomy import load_studio_schema


@dataclass(frozen=True, slots=True)
class Finding:
    severity: str
    field_key: str
    message: str
    fix_hint: str
    tier: str

    def as_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "field_key": self.field_key,
            "message": self.message,
            "fix_hint": self.fix_hint,
            "tier": self.tier,
        }


def field_catalog() -> dict[str, dict[str, Any]]:
    return {field["field_key"]: field for field in load_studio_schema()["fields"]}


def validate_value(field: dict[str, Any], value: str, unit: str | None = None) -> str:
    dtype = field["dtype"]
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Value cannot be empty")
    if dtype == "integer":
        number = Decimal(cleaned.replace(",", ""))
        if number != number.to_integral_value():
            raise ValueError("Expected a whole number")
        cleaned = str(int(number))
    elif dtype == "number":
        try:
            cleaned = format(Decimal(cleaned.replace(",", "")), "f")
        except InvalidOperation as exc:
            raise ValueError("Expected a number") from exc
    elif dtype == "boolean":
        lowered = cleaned.lower()
        if lowered not in {"true", "false", "yes", "no"}:
            raise ValueError("Expected true/false or yes/no")
        cleaned = "true" if lowered in {"true", "yes"} else "false"
    elif dtype == "date":
        date.fromisoformat(cleaned)
    if field.get("repeating_group"):
        try:
            rows = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError("Repeating groups must be a JSON array") from exc
        if not isinstance(rows, list):
            raise ValueError("Repeating groups must be a JSON array")
    expected_unit = field.get("unit")
    if expected_unit and unit != expected_unit:
        raise ValueError(f"Expected unit {expected_unit}")
    if expected_unit == "percent" and not 0 <= Decimal(cleaned) <= 100:
        raise ValueError("Percentage must be between 0 and 100")
    return cleaned


def _required(field: dict[str, Any], answers: dict[str, str]) -> bool:
    if not field.get("required", True) or field.get("leadership"):
        return False
    condition = field.get("condition")
    if not condition:
        return True
    left, operator, right = str(condition).split()
    candidates = [left, f"a.basics.{left}"]
    actual = next((answers[key] for key in candidates if key in answers), None)
    return operator == "==" and actual == right


def validate_filing(
    answers: dict[str, str],
    *,
    answer_meta: dict[str, dict[str, Any]] | None = None,
    prior_answers: dict[str, str] | None = None,
    yoy_threshold_pct: Decimal = Decimal("50"),
) -> list[Finding]:
    schema = load_studio_schema()
    catalog = {field["field_key"]: field for field in schema["fields"]}
    findings: list[Finding] = []
    for key, value in answers.items():
        field = catalog.get(key)
        if field is None:
            findings.append(Finding("error", key, "Unknown field", "Remove this answer", "L1"))
            continue
        try:
            validate_value(field, value, field.get("unit"))
        except (ValueError, InvalidOperation) as exc:
            findings.append(Finding("error", key, str(exc), "Correct the value", "L1"))
    for relation in schema.get("relations", []):
        target = relation["target"]
        operands = relation["operands"]
        if target not in answers or not all(key in answers for key in operands):
            continue
        try:
            actual = Decimal(answers[target])
            expected = sum(Decimal(answers[key]) for key in operands)
        except InvalidOperation:
            continue
        tolerance = Decimal(str(relation.get("tolerance", 0)))
        if abs(actual - expected) > tolerance:
            findings.append(
                Finding(
                    "error",
                    target,
                    f"Total {actual} does not equal component sum {expected}",
                    "Reconcile the total with its component values",
                    "L2",
                )
            )
    if prior_answers:
        for key, current in answers.items():
            if key not in prior_answers or catalog.get(key, {}).get("dtype") not in {
                "number",
                "integer",
            }:
                continue
            previous = Decimal(prior_answers[key])
            if previous and abs((Decimal(current) - previous) / previous * 100) > yoy_threshold_pct:
                findings.append(
                    Finding(
                        "warning",
                        key,
                        f"Year-on-year movement exceeds {yoy_threshold_pct}%",
                        "Confirm the change and add supporting evidence",
                        "L2",
                    )
                )
    for field in schema["fields"]:
        key = field["field_key"]
        if _required(field, answers) and key not in answers:
            findings.append(
                Finding("error", key, "Required answer is missing", "Complete this field", "L3")
            )
    for key, meta in (answer_meta or {}).items():
        if meta.get("author") == "ai" and meta.get("review_status") == "unreviewed":
            findings.append(
                Finding(
                    "error",
                    key,
                    "AI-proposed answer has not been reviewed",
                    "Accept, edit-accept, or reject the proposal",
                    "L3",
                )
            )
    return findings


def progress(
    answers: dict[str, str], answer_meta: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    schema = load_studio_schema()
    eligible = {
        key
        for key in answers
        if not (
            (answer_meta or {}).get(key, {}).get("author") == "ai"
            and (answer_meta or {}).get(key, {}).get("review_status") == "unreviewed"
        )
    }
    groups: dict[str, list[dict[str, Any]]] = {}
    for field in schema["fields"]:
        groups.setdefault(str(field["principle"]), []).append(field)
    sections = {}
    for name, fields in groups.items():
        required = [field for field in fields if _required(field, answers)]
        done = sum(field["field_key"] in eligible for field in required)
        sections[name] = round(100 * done / len(required)) if required else 100
    core = [field for field in schema["fields"] if field.get("core_kpi")]
    core_done = sum(field["field_key"] in eligible for field in core)
    return {
        "sections": sections,
        "overall_pct": round(sum(sections.values()) / len(sections)) if sections else 0,
        "core_pct": round(100 * core_done / len(core)) if core else 100,
        "complete": all(value == 100 for value in sections.values()),
    }


def prior_prefill_candidates(
    current_answers: dict[str, str], prior_answers: dict[str, str]
) -> list[dict[str, str]]:
    return [
        {"field_key": key, "value": value, "status": "candidate", "author_after_accept": "user"}
        for key, value in prior_answers.items()
        if key not in current_answers and key in field_catalog()
    ]
