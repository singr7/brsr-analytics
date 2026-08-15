from pathlib import Path
from typing import Annotated
from uuid import UUID

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.access import CurrentUser, optional_user
from api.app.db.session import get_db_session
from api.app.models import (
    Company,
    CompanyAnnotation,
    CorrectionTicket,
    ExtractedField,
    FieldDef,
    FieldVersionPin,
    Filing,
    FilingPage,
    LibraryExemplar,
    LibraryPattern,
    Score,
    User,
)
from api.app.schemas.trust import AnnotationCreate, IssueCreate, PatternCreate
from worker.parse.embeddings import hash_embedding

router = APIRouter(prefix="/api", tags=["trust"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
ROOT = Path(__file__).resolve().parents[3]


@router.get("/lineage/{pin_id}")
async def lineage(pin_id: UUID, session: SessionDep) -> dict[str, object]:
    row = (
        await session.execute(
            select(FieldVersionPin, ExtractedField, Filing, FilingPage, FieldDef)
            .join(ExtractedField, ExtractedField.id == FieldVersionPin.extracted_field_id)
            .join(Filing, Filing.id == FieldVersionPin.filing_id)
            .join(FieldDef, FieldDef.field_key == FieldVersionPin.field_key)
            .outerjoin(
                FilingPage,
                (FilingPage.filing_id == Filing.id)
                & (FilingPage.page_no == ExtractedField.source_page),
            )
            .where(FieldVersionPin.id == pin_id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lineage reference not found")
    pin, field, filing, page, definition = row
    annotations = list(
        await session.scalars(
            select(CompanyAnnotation).where(
                CompanyAnnotation.field_version_pin_id == pin.id,
                CompanyAnnotation.status == "published",
            )
        )
    )
    return {
        "pin_id": str(pin.id),
        "filing_id": str(filing.id),
        "field": {
            "key": field.field_key,
            "label": definition.label,
            "value": field.value_raw,
            "unit": field.unit,
            "method": field.method,
            "confidence": field.confidence,
            "qa_status": field.qa_status,
            "version": field.version,
        },
        "source": {
            "page": field.source_page,
            "span": field.source_span,
            "text": page.text if page else None,
            "image_url": page.s3_image if page else None,
            "table_regions": page.table_regions if page else [],
        },
        "annotations": [
            {"id": str(item.id), "body": item.body, "created_at": item.created_at}
            for item in annotations
        ],
    }


@router.post("/corrections", status_code=status.HTTP_201_CREATED)
async def report_issue(
    payload: IssueCreate,
    session: SessionDep,
    user: Annotated[User | None, Depends(optional_user)],
) -> dict[str, object]:
    if await session.get(FieldVersionPin, payload.pin_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lineage reference not found")
    ticket = CorrectionTicket(
        field_version_pin_id=payload.pin_id,
        reporter_user_id=user.id if user else None,
        description=payload.description,
    )
    session.add(ticket)
    await session.commit()
    return {"id": str(ticket.id), "status": ticket.status, "sla": "Acknowledged within 5 days"}


@router.post("/annotations", status_code=status.HTTP_201_CREATED)
async def add_annotation(
    payload: AnnotationCreate, user: CurrentUser, session: SessionDep
) -> dict[str, object]:
    pin = await session.get(FieldVersionPin, payload.pin_id)
    if pin is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lineage reference not found")
    filing = await session.get(Filing, pin.filing_id)
    if filing is None or filing.company_id != payload.company_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Pin does not match company")
    annotation = CompanyAnnotation(
        company_id=payload.company_id,
        field_version_pin_id=payload.pin_id,
        author_user_id=user.id,
        body=payload.body,
    )
    session.add(annotation)
    await session.commit()
    return {"id": str(annotation.id), "status": annotation.status}


@router.get("/library")
async def library_search(
    session: SessionDep,
    user: Annotated[User | None, Depends(optional_user)],
    q: Annotated[str | None, Query(max_length=300)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 12,
) -> dict[str, object]:
    statement = select(LibraryPattern).where(LibraryPattern.is_published.is_(True))
    patterns = list(await session.scalars(statement.order_by(LibraryPattern.title)))
    if q:
        query_vector = hash_embedding(q)
        patterns.sort(
            key=lambda item: _similarity(
                query_vector, hash_embedding(f"{item.title} {item.topic} {item.pattern_note}")
            ),
            reverse=True,
        )
    patterns = patterns[:limit]
    full = user is not None and user.plan_tier in {"pro", "studio", "research"}
    exemplar_rows = (
        (
            await session.execute(
                select(LibraryExemplar, FilingPage, Filing, Company)
                .join(FilingPage, FilingPage.id == LibraryExemplar.filing_page_id)
                .join(Filing, Filing.id == FilingPage.filing_id)
                .join(Company, Company.id == Filing.company_id)
                .where(LibraryExemplar.pattern_id.in_([item.id for item in patterns]))
            )
        ).all()
        if patterns and full
        else []
    )
    exemplars: dict[UUID, list[dict[str, object]]] = {}
    for exemplar, page, filing, company in exemplar_rows:
        exemplars.setdefault(exemplar.pattern_id, []).append(
            {
                "excerpt": exemplar.excerpt,
                "page": page.page_no,
                "fy": filing.fy,
                "company": company.name if exemplar.company_permission else "Anonymised leader",
            }
        )
    filing_matches: list[dict[str, object]] = []
    if q and full:
        latest = select(func.max(Score.method_version)).scalar_subquery()
        pages = (
            await session.execute(
                select(FilingPage, Filing, Company)
                .join(Filing, Filing.id == FilingPage.filing_id)
                .join(Company, Company.id == Filing.company_id)
                .join(Score, (Score.company_id == Company.id) & (Score.fy == Filing.fy))
                .where(
                    Score.score_key == "substance",
                    Score.method_version == latest,
                    Score.value >= 70,
                )
                .limit(100)
            )
        ).all()
        query_vector = hash_embedding(q)
        ranked = sorted(
            pages,
            key=lambda row: _similarity(query_vector, hash_embedding(row[0].text)),
            reverse=True,
        )[:5]
        filing_matches = [
            {
                "excerpt": page.text[:500],
                "page": page.page_no,
                "fy": filing.fy,
                "company": "Anonymised high-substance company",
            }
            for page, filing, _company in ranked
        ]
    return {
        "access": "full" if full else "teaser",
        "items": [
            {
                "id": str(item.id),
                "title": item.title,
                "topic": item.topic,
                "pattern_note": item.pattern_note if full else item.pattern_note[:180],
                "exemplars": exemplars.get(item.id, []),
            }
            for item in patterns
        ],
        "filing_matches": filing_matches,
    }


def _similarity(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


@router.post("/admin/library", status_code=status.HTTP_201_CREATED)
async def create_pattern(
    payload: PatternCreate, user: CurrentUser, session: SessionDep
) -> dict[str, object]:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Platform admin required")
    pattern = LibraryPattern(**payload.model_dump())
    session.add(pattern)
    await session.commit()
    return {"id": str(pattern.id), "published": pattern.is_published}


@router.get("/methodology")
async def methodology(session: SessionDep) -> dict[str, object]:
    scoring = yaml.safe_load((ROOT / "scoring.yaml").read_text())
    principle_rows = (
        await session.execute(
            select(FieldDef.principle, func.count()).group_by(FieldDef.principle)
        )
    ).all()
    return {
        "method_version": scoring["method_version"],
        "minimum_cohort_size": scoring["minimum_sector_size"],
        "coverage": [{"principle": key, "fields": count} for key, count in principle_rows],
        "changelog": [
            {
                "version": scoring["method_version"],
                "summary": "Initial pinned-data completeness, substance, and assurance method.",
            }
        ],
        "correction_sla": "Reports are acknowledged within 5 business days and resolved visibly.",
    }
