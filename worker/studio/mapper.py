from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from api.app.db.taxonomy import load_studio_schema
from worker.studio.documents import retrieve


@dataclass(frozen=True, slots=True)
class Proposal:
    field_key: str
    proposed_value: str
    unit: str | None
    doc_id: str
    page: int
    quote: str
    confidence: float

    def as_dict(self) -> dict[str, object]:
        return {
            "field_key": self.field_key,
            "proposed_value": self.proposed_value,
            "unit": self.unit,
            "evidence": {"doc_id": self.doc_id, "page": self.page, "quote": self.quote},
            "confidence": self.confidence,
            "review_status": "unreviewed",
        }


def quote_is_verbatim(quote: str, source_text: str) -> bool:
    normalized_quote = " ".join(quote.split()).casefold()
    normalized_source = " ".join(source_text.split()).casefold()
    return bool(normalized_quote) and normalized_quote in normalized_source


def propose_for_section(
    section: str,
    documents: list[dict[str, Any]],
    *,
    studio_org_id: str,
    existing_user_fields: set[str] | None = None,
) -> list[Proposal]:
    schema = load_studio_schema()
    fields = [field for field in schema["fields"] if field["section"] == section]
    proposals: list[Proposal] = []
    for field in fields:
        if field["field_key"] in (existing_user_fields or set()):
            continue
        evidence = retrieve(
            f"{field['label']} {field['field_key']}",
            documents,
            studio_org_id=studio_org_id,
            limit=1,
        )
        if not evidence:
            continue
        candidate = evidence[0]
        source = str(candidate["text"])
        quote = source[:280].strip()
        value = _candidate_value(field, source)
        if value is None or not quote_is_verbatim(quote, source):
            continue
        proposals.append(
            Proposal(
                field_key=field["field_key"],
                proposed_value=value,
                unit=field.get("unit"),
                doc_id=str(candidate["doc_id"]),
                page=int(candidate["page"]),
                quote=quote,
                confidence=min(0.98, 0.7 + float(candidate["score"])),
            )
        )
    return proposals


def _candidate_value(field: dict[str, Any], text: str) -> str | None:
    if field["dtype"] in {"number", "integer"}:
        match = re.search(r"(?<![A-Za-z])([0-9][0-9,]*(?:\.[0-9]+)?)", text)
        if not match:
            return None
        value = match.group(1).replace(",", "")
        return str(int(float(value))) if field["dtype"] == "integer" else value
    if field["dtype"] == "boolean":
        lowered = text.lower()
        return (
            "true" if any(word in lowered for word in ("yes", "approved", "available")) else "false"
        )
    return text.strip()[:500] or None


DOCUMENT_RECOMMENDATIONS = {
    "A": "Upload the prior BRSR, annual report, entity master and CSR report.",
    "P3": "Upload HR headcount, benefits, safety and training registers.",
    "P5": "Upload the human-rights policy, grievance register and assessment report.",
    "P6": "Upload utility bills, water statements, emissions inventory and waste manifests.",
}


def document_gap_report(proposals: list[Proposal], accepted_fields: set[str]) -> dict[str, object]:
    schema = load_studio_schema()
    evidence_fields = accepted_fields | {item.field_key for item in proposals}
    gaps = []
    principles = sorted({str(field["principle"]) for field in schema["fields"]})
    for principle in principles:
        fields = [
            field["field_key"] for field in schema["fields"] if field["principle"] == principle
        ]
        covered = sum(key in evidence_fields for key in fields)
        if not covered:
            gaps.append(
                {
                    "section": principle,
                    "coverage_pct": 0,
                    "recommendation": DOCUMENT_RECOMMENDATIONS.get(
                        principle, "Upload policies, registers and measured KPI source records."
                    ),
                }
            )
    return {"evidence_fields": len(evidence_fields), "gaps": gaps}


def within_token_quota(used: int, estimated: int, limit: int) -> bool:
    return used >= 0 and estimated >= 0 and used + estimated <= limit
