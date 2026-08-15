from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from api.app.core.access import CurrentUser, SessionDep
from api.app.core.config import Settings, get_settings
from api.app.models import ExtractedField, FilingPage, QAReview, QualityStat
from api.app.routers.acquisition import require_platform_admin
from api.app.schemas.quality import (
    QualityFamily,
    QualityResponse,
    ReviewDecision,
    ReviewItem,
    ReviewResult,
)
from api.app.services.quality import complete_review, enqueue_sample
from worker.score.tasks import pin_changed_task

router = APIRouter(
    prefix="/api/admin", tags=["quality"], dependencies=[Depends(require_platform_admin)]
)


@router.post("/reviews/sample")
async def sample_reviews(
    session: SessionDep, per_stratum: Annotated[int, Query(ge=1, le=100)] = 5
) -> dict[str, int]:
    return {"queued": await enqueue_sample(session, per_stratum=per_stratum)}


@router.get("/reviews", response_model=list[ReviewItem])
async def review_queue(session: SessionDep) -> list[ReviewItem]:
    rows = (
        await session.execute(
            select(QAReview, ExtractedField, FilingPage)
            .join(ExtractedField, ExtractedField.id == QAReview.extracted_field_id)
            .outerjoin(
                FilingPage,
                (FilingPage.filing_id == ExtractedField.filing_id)
                & (FilingPage.page_no == ExtractedField.source_page),
            )
            .where(QAReview.status == "queued")
            .order_by(QAReview.created_at)
        )
    ).all()
    items: list[ReviewItem] = []
    for review, field, page in rows:
        span = field.source_span or {}
        items.append(
            ReviewItem(
                review_id=review.id,
                extracted_field_id=field.id,
                field_key=field.field_key,
                value_raw=field.value_raw,
                confidence=field.confidence,
                source_page=field.source_page,
                source_quote=str(span.get("quote")) if span.get("quote") else None,
                page_image=page.s3_image if page else None,
                family=review.family,
                confidence_band=review.confidence_band,
                queued_at=review.created_at,
            )
        )
    return items


@router.patch("/reviews/{review_id}", response_model=ReviewResult)
async def decide_review(
    review_id: UUID,
    body: ReviewDecision,
    session: SessionDep,
    user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReviewResult:
    try:
        review, field, reasons = await complete_review(
            session,
            review_id,
            user,
            settings,
            corrected_value=body.corrected_value,
            corrected_numeric=body.corrected_numeric,
            corrected_unit=body.corrected_unit,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    if not reasons:
        pin_changed_task.delay()
    return ReviewResult(
        review_id=review.id,
        status=review.status,
        extracted_field_id=field.id,
        pinned=not reasons,
        policy_reasons=list(reasons),
    )


@router.get("/quality", response_model=QualityResponse)
async def quality_stats(session: SessionDep) -> QualityResponse:
    stats = (await session.scalars(select(QualityStat).order_by(QualityStat.family))).all()
    return QualityResponse(
        families=[
            QualityFamily(
                family=stat.family,
                reviewed_count=stat.reviewed_count,
                correct_count=stat.correct_count,
                accuracy=stat.accuracy,
            )
            for stat in stats
        ]
    )
