from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.models import ExtractedField, FieldDef, Filing, FilingPage, LLMUsage
from api.app.services.llm import LLMClient, LLMError
from worker.extract.contracts import ExtractionResponse
from worker.extract.hygiene import parse_numeric
from worker.extract.validation import ValidatedExtraction, validate_extraction


@dataclass(frozen=True, slots=True)
class BatchResult:
    fields: list[ValidatedExtraction]
    input_tokens: int
    output_tokens: int


async def extract_batch(
    llm: LLMClient,
    section: str,
    field_defs: list[dict[str, Any]],
    pages: dict[int, str],
    *,
    page_images: dict[int, str] | None = None,
    attempts: int = 3,
) -> BatchResult:
    variables = {
        "section": section,
        "field_defs": json.dumps(field_defs, sort_keys=True),
        "pages": json.dumps(pages, sort_keys=True),
        "page_images": json.dumps(page_images or {}, sort_keys=True),
    }
    response: ExtractionResponse | None = None
    for attempt in range(attempts):
        try:
            response = await llm.complete("extract_section", "v1", variables, ExtractionResponse)
            break
        except LLMError:
            if attempt == attempts - 1:
                raise
            await asyncio.sleep(0)
    if response is None:  # pragma: no cover - loop contract
        raise LLMError("Extraction attempts exhausted")
    allowed = {str(definition["field_key"]) for definition in field_defs}
    validated = [validate_extraction(item, pages, allowed) for item in response.fields]
    prompt_chars = sum(len(str(value)) for value in variables.values())
    output_chars = len(response.model_dump_json())
    return BatchResult(validated, max(1, prompt_chars // 4), max(1, output_chars // 4))


async def run_extraction(
    session: AsyncSession,
    filing_id: UUID,
    llm: LLMClient,
    *,
    attempts: int = 3,
) -> int:
    filing = await session.get(Filing, filing_id)
    if filing is None or filing.status != "parsed":
        raise ValueError("Only parsed filings can be extracted")
    has_xbrl = exists().where(
        ExtractedField.filing_id == filing.id,
        ExtractedField.field_key == FieldDef.field_key,
        ExtractedField.method == "xbrl",
    )
    definitions = (await session.scalars(select(FieldDef).where(~has_xbrl))).all()
    pages = (
        await session.scalars(
            select(FilingPage).where(FilingPage.filing_id == filing.id).order_by(FilingPage.page_no)
        )
    ).all()
    pages_by_section: dict[str, dict[int, str]] = {}
    images_by_section: dict[str, dict[int, str]] = {}
    for page in pages:
        page_section = page.section_key or "unclassified"
        pages_by_section.setdefault(page_section, {})[page.page_no] = page.text
        if page.table_regions and page.s3_image:
            images_by_section.setdefault(page_section, {})[page.page_no] = page.s3_image
    defs_by_section: dict[str, list[FieldDef]] = {}
    for definition in definitions:
        defs_by_section.setdefault(definition.section, []).append(definition)
    max_version = int(
        (
            await session.scalar(
                select(func.max(ExtractedField.version)).where(
                    ExtractedField.filing_id == filing.id
                )
            )
        )
        or 0
    )
    version = max_version + 1
    created = 0
    all_pages = {page.page_no: page.text for page in pages}
    for section, section_defs in defs_by_section.items():
        page_subset = pages_by_section.get(section) or all_pages
        if not page_subset:
            continue
        serialized_defs = [
            {
                "field_key": definition.field_key,
                "label": definition.label,
                "dtype": definition.dtype,
                "unit": definition.unit,
            }
            for definition in section_defs
        ]
        result = await extract_batch(
            llm,
            section,
            serialized_defs,
            page_subset,
            page_images=images_by_section.get(section, {}),
            attempts=attempts,
        )
        session.add(
            LLMUsage(
                filing_id=filing.id,
                prompt_key="extract_section",
                prompt_version="v1",
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cost_usd=(
                    Decimal(result.input_tokens) * Decimal("0.0000004")
                    + Decimal(result.output_tokens) * Decimal("0.0000016")
                ),
            )
        )
        definition_by_key = {definition.field_key: definition for definition in section_defs}
        for validated in result.fields:
            item = validated.item
            target_def = definition_by_key.get(item.field_key)
            if target_def is None or item.not_found or item.value is None:
                continue
            raw = str(item.value)
            numeric = parse_numeric(raw) if target_def.dtype in {"number", "integer"} else None
            flags = list(validated.flags)
            confidence = validated.confidence
            if numeric is not None and numeric.value is None:
                flags.append("numeric_parse_failed")
                confidence *= 0.5
            quote = item.source_quote or ""
            page_text = page_subset.get(item.source_page or -1, "")
            start = page_text.find(quote) if quote else -1
            session.add(
                ExtractedField(
                    filing_id=filing.id,
                    field_key=item.field_key,
                    value_raw=raw,
                    value_num=numeric.value if numeric else None,
                    unit=item.unit or target_def.unit,
                    confidence=Decimal(str(confidence)),
                    method="llm",
                    source_page=item.source_page,
                    source_span={
                        "start": start if start >= 0 else None,
                        "end": start + len(quote) if start >= 0 else None,
                        "quote": quote,
                        "flags": flags,
                        "prompt": "extract_section@v1",
                    },
                    qa_status="unreviewed",
                    version=version,
                )
            )
            created += 1
    await session.commit()
    return created
