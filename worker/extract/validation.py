from __future__ import annotations

from dataclasses import dataclass

from worker.extract.contracts import ExtractionItem


@dataclass(frozen=True, slots=True)
class ValidatedExtraction:
    item: ExtractionItem
    confidence: float
    flags: tuple[str, ...]


def validate_extraction(
    item: ExtractionItem, page_text_by_number: dict[int, str], allowed_fields: set[str]
) -> ValidatedExtraction:
    flags: list[str] = []
    confidence = item.confidence
    if item.field_key not in allowed_fields:
        flags.append("unexpected_field")
        confidence = 0.0
    if item.not_found:
        return ValidatedExtraction(item, 0.0, tuple(flags + ["not_found"]))
    page_text = page_text_by_number.get(item.source_page or -1)
    if not item.source_quote or page_text is None or item.source_quote not in page_text:
        flags.append("source_quote_not_verbatim")
        confidence = 0.0
    return ValidatedExtraction(item, confidence, tuple(flags))
