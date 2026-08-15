from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True, slots=True)
class NumericValue:
    value: Decimal | None
    lower: Decimal | None = None
    upper: Decimal | None = None
    is_percent: bool = False
    is_nil: bool = False


_SCALE = {"lakh": Decimal("100000"), "lac": Decimal("100000"), "crore": Decimal("10000000")}


def _number(value: str) -> Decimal:
    return Decimal(value.replace(",", "").strip())


def parse_numeric(raw: str) -> NumericValue:
    text = raw.strip().lower().replace("₹", "").replace("inr", "")
    if text in {"nil", "none", "zero", "-", "—"}:
        return NumericValue(Decimal(0), is_nil=True)
    is_percent = "%" in text or "percent" in text
    scale = Decimal(1)
    for name, factor in _SCALE.items():
        if re.search(rf"\b{name}s?\b", text):
            scale = factor
            break
    matches = re.findall(r"[-+]?\d[\d,]*(?:\.\d+)?", text)
    if not matches:
        return NumericValue(None)
    try:
        numbers = [_number(value) * scale for value in matches]
    except InvalidOperation:
        return NumericValue(None)
    if len(numbers) >= 2 and re.search(r"\b(?:to|through)\b|[–—]", text):
        lower, upper = sorted(numbers[:2])
        return NumericValue((lower + upper) / 2, lower, upper, is_percent)
    return NumericValue(numbers[0], is_percent=is_percent)


@dataclass(frozen=True, slots=True)
class RelationCheck:
    passed: bool
    relative_error: Decimal
    flag: str | None


def check_total_relation(
    total: Decimal,
    parts: list[Decimal],
    *,
    tolerance: Decimal = Decimal("0.02"),
) -> RelationCheck:
    difference = abs(total - sum(parts, Decimal(0)))
    relative = difference / max(abs(total), Decimal(1))
    passed = relative <= tolerance
    return RelationCheck(passed, relative, None if passed else "declared_total_mismatch")
