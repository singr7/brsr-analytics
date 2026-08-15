from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class UnitSpec:
    family: str
    canonical: str
    factor: Decimal


_UNITS = {
    "gj": UnitSpec("energy", "GJ", Decimal("1")),
    "kwh": UnitSpec("energy", "GJ", Decimal("0.0036")),
    "mwh": UnitSpec("energy", "GJ", Decimal("3.6")),
    "kl": UnitSpec("water", "KL", Decimal("1")),
    "kilolitre": UnitSpec("water", "KL", Decimal("1")),
    "kilolitres": UnitSpec("water", "KL", Decimal("1")),
    "ml": UnitSpec("water", "KL", Decimal("1000")),
    "megalitre": UnitSpec("water", "KL", Decimal("1000")),
    "megalitres": UnitSpec("water", "KL", Decimal("1000")),
    "tco2e": UnitSpec("emissions", "tCO2e", Decimal("1")),
    "kgco2e": UnitSpec("emissions", "tCO2e", Decimal("0.001")),
    "mtco2e": UnitSpec("emissions", "tCO2e", Decimal("1000000")),
    "mt": UnitSpec("mass", "MT", Decimal("1")),
    "kg": UnitSpec("mass", "MT", Decimal("0.001")),
    "percent": UnitSpec("percentage", "percent", Decimal("1")),
    "%": UnitSpec("percentage", "percent", Decimal("1")),
    "count": UnitSpec("count", "count", Decimal("1")),
    "inr": UnitSpec("currency", "INR", Decimal("1")),
}


def unit_spec(unit: str) -> UnitSpec:
    key = unit.strip().lower().replace(" ", "")
    try:
        return _UNITS[key]
    except KeyError as exc:
        raise ValueError(f"Unsupported unit: {unit}") from exc


def convert_unit(
    value: Decimal | int | float | str, source_unit: str, target_unit: str | None = None
) -> tuple[Decimal, str]:
    """Convert to the family's canonical unit, or to another compatible known unit."""
    source = unit_spec(source_unit)
    canonical_value = Decimal(str(value)) * source.factor
    if target_unit is None:
        return canonical_value, source.canonical
    target = unit_spec(target_unit)
    if target.family != source.family:
        raise ValueError(f"Incompatible units: {source_unit} and {target_unit}")
    return canonical_value / target.factor, target.canonical
