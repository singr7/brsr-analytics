from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import PurePosixPath
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.models import Embedding, ExtractedField, FieldDef, Filing, FilingPage
from api.app.services.storage import ObjectStore
from worker.parse.embeddings import hash_embedding
from worker.parse.pdf import parse_pdf
from worker.parse.xbrl import parse_xbrl


async def parse_filing(
    session: AsyncSession,
    store: ObjectStore,
    filing_id: UUID,
    *,
    embedding_model: str = "hash-embedding-v1",
) -> Filing:
    filing = await session.get(Filing, filing_id)
    if filing is None:
        raise ValueError("Filing not found")
    if filing.status not in {"fetched", "parsed"} or not filing.s3_raw:
        raise ValueError("Only fetched filings with a raw object can be parsed")
    content = store.get(filing.s3_raw)
    parse_version = filing.parse_version + 1
    filename = (filing.filename or filing.s3_raw).lower()
    is_xbrl = filename.endswith((".xbrl", ".xml", ".xhtml")) or content.lstrip().startswith(
        b"<?xml"
    )
    filing.parsed_at = datetime.now(UTC)
    filing.parse_version = parse_version
    filing.parsed_pages = 0
    filing.sections_found = 0
    filing.xbrl_fact_count = 0
    filing.section_confidence = None

    if is_xbrl:
        definitions = (await session.scalars(select(FieldDef))).all()
        mapping = {
            definition.xbrl_concept: (definition.field_key, definition.unit)
            for definition in definitions
            if definition.xbrl_concept
        }
        facts = parse_xbrl(content, mapping)
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
        for fact in facts:
            session.add(
                ExtractedField(
                    filing_id=filing.id,
                    field_key=fact.field_key,
                    value_raw=fact.value_raw,
                    value_num=fact.value_num,
                    unit=fact.unit,
                    confidence=Decimal("1.0"),
                    method="xbrl",
                    source_page=None,
                    source_span={
                        "context_id": fact.context_id,
                        "period_start": fact.period_start.isoformat()
                        if fact.period_start
                        else None,
                        "period_end": fact.period_end.isoformat() if fact.period_end else None,
                        "decimals": fact.decimals,
                        "parse_version": parse_version,
                    },
                    qa_status="unreviewed",
                    version=version,
                )
            )
        filing.xbrl_fact_count = len(facts)
    else:
        old_page_ids = list(
            await session.scalars(select(FilingPage.id).where(FilingPage.filing_id == filing.id))
        )
        if old_page_ids:
            await session.execute(
                delete(Embedding).where(
                    Embedding.owner_kind == "filing_page", Embedding.owner_id.in_(old_page_ids)
                )
            )
        await session.execute(delete(FilingPage).where(FilingPage.filing_id == filing.id))
        pages, location = parse_pdf(content)
        for parsed in pages:
            key = str(
                PurePosixPath("pages", str(filing.id), f"v{parse_version}", f"{parsed.page_no}.png")
            )
            uri = store.put(key, parsed.image_png, "image/png")
            page = FilingPage(
                filing_id=filing.id,
                page_no=parsed.page_no,
                text=parsed.text,
                s3_image=uri,
                parse_version=parse_version,
                section_key=parsed.section_key,
                locator_confidence=Decimal(str(parsed.locator_confidence)),
                table_regions=[asdict(region) for region in parsed.table_regions],
            )
            session.add(page)
            await session.flush()
            session.add(
                Embedding(
                    owner_kind="filing_page",
                    owner_id=page.id,
                    embedding=hash_embedding(parsed.text),
                    model=embedding_model,
                )
            )
        filing.parsed_pages = len(pages)
        filing.sections_found = len(set(location.page_sections.values()))
        filing.section_confidence = Decimal(str(location.confidence))
    filing.status = "parsed"
    await session.commit()
    await session.refresh(filing)
    return filing
