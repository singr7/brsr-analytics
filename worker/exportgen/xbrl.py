from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from api.app.db.taxonomy import load_studio_schema
from worker.studio.engine import Finding, validate_filing

NS_XBRLI = "http://www.xbrl.org/2003/instance"
NS_ISO4217 = "http://www.xbrl.org/2003/iso4217"
ET.register_namespace("xbrli", NS_XBRLI)
ET.register_namespace("iso4217", NS_ISO4217)
ET.register_namespace("brsr", "https://brsrlens.local/taxonomy/brsr/2024")


@dataclass(frozen=True, slots=True)
class ExportGate:
    allowed: bool
    findings: list[Finding]


def export_gate(
    answers: dict[str, str],
    answer_meta: dict[str, dict[str, Any]],
    arelle_findings: list[Finding] | None = None,
) -> ExportGate:
    findings = validate_filing(answers, answer_meta=answer_meta) + (arelle_findings or [])
    blocked = any(item.severity == "error" for item in findings)
    return ExportGate(allowed=not blocked, findings=findings)


def generate_instance(answers: dict[str, str], *, entity_identifier: str, fy: int) -> bytes:
    schema = load_studio_schema()
    catalog = {field["field_key"]: field for field in schema["fields"]}
    root = ET.Element(f"{{{NS_XBRLI}}}xbrl")
    context = ET.SubElement(root, f"{{{NS_XBRLI}}}context", {"id": f"FY{fy}"})
    entity = ET.SubElement(context, f"{{{NS_XBRLI}}}entity")
    identifier = ET.SubElement(
        entity,
        f"{{{NS_XBRLI}}}identifier",
        {"scheme": "https://www.mca.gov.in/CIN"},
    )
    identifier.text = entity_identifier
    period = ET.SubElement(context, f"{{{NS_XBRLI}}}period")
    ET.SubElement(period, f"{{{NS_XBRLI}}}startDate").text = f"{fy - 1}-04-01"
    ET.SubElement(period, f"{{{NS_XBRLI}}}endDate").text = f"{fy}-03-31"
    for unit_id, measure in (
        ("count", "xbrli:pure"),
        ("percent", "xbrli:pure"),
        ("INR", "iso4217:INR"),
        ("GJ", "brsr:GJ"),
        ("kL", "brsr:kL"),
        ("tCO2e", "brsr:tCO2e"),
        ("MT", "brsr:MT"),
    ):
        unit = ET.SubElement(root, f"{{{NS_XBRLI}}}unit", {"id": unit_id})
        ET.SubElement(unit, f"{{{NS_XBRLI}}}measure").text = measure
    for key, value in sorted(answers.items()):
        field = catalog.get(key)
        if field is None:
            continue
        attributes = {"contextRef": f"FY{fy}"}
        if field["dtype"] in {"number", "integer"}:
            attributes["unitRef"] = str(field.get("unit") or "count")
            attributes["decimals"] = "0" if field["dtype"] == "integer" else "2"
            value = format(Decimal(value), "f")
        fact = ET.SubElement(
            root,
            f"{{https://brsrlens.local/taxonomy/brsr/2024}}{field['xbrl_concept']}",
            attributes,
        )
        fact.text = value
    return bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))


def validate_instance(instance: bytes) -> list[Finding]:
    try:
        root = ET.fromstring(instance)
    except ET.ParseError as exc:
        return [Finding("error", "xbrl", str(exc), "Regenerate the instance", "arelle")]
    if not root.findall(f"{{{NS_XBRLI}}}context"):
        return [
            Finding("error", "xbrl", "Instance has no context", "Add a reporting context", "arelle")
        ]
    return []


def arelle_validate(instance: bytes) -> list[Finding]:
    executable = shutil.which("arelleCmdLine")
    if executable is None:
        return validate_instance(instance)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "filing.xbrl"
        path.write_bytes(instance)
        result = subprocess.run(
            [executable, "--file", str(path), "--validate"],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    messages = [
        line for line in (result.stdout + result.stderr).splitlines() if "error" in line.lower()
    ]
    return [
        Finding("error", "xbrl", message, "Resolve the taxonomy validation error", "arelle")
        for message in messages
    ]
