from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.config import Settings
from api.app.models import ExtractedField, QAReview, QualityStat, User
from api.app.services.publication_policy import field_family, update_pin_if_publishable


def confidence_band(confidence: Decimal | None) -> str:
    value = confidence or Decimal(0)
    if value >= Decimal("0.90"):
        return "high"
    if value >= Decimal("0.70"):
        return "medium"
    return "low"


def stratified_sample(
    fields: list[ExtractedField], *, per_stratum: int = 5
) -> list[ExtractedField]:
    strata: dict[tuple[str, str], list[ExtractedField]] = {}
    for field in fields:
        key = (field_family(field.field_key), confidence_band(field.confidence))
        strata.setdefault(key, []).append(field)
    sampled: list[ExtractedField] = []
    for key in sorted(strata):
        sampled.extend(sorted(strata[key], key=lambda item: str(item.id))[:per_stratum])
    return sampled


async def enqueue_sample(session: AsyncSession, *, per_stratum: int = 5) -> int:
    queued_ids = select(QAReview.extracted_field_id)
    fields = list(
        await session.scalars(
            select(ExtractedField).where(
                ExtractedField.method == "llm",
                ExtractedField.qa_status == "unreviewed",
                ExtractedField.id.not_in(queued_ids),
            )
        )
    )
    selected = stratified_sample(fields, per_stratum=per_stratum)
    for field in selected:
        session.add(
            QAReview(
                extracted_field_id=field.id,
                family=field_family(field.field_key),
                confidence_band=confidence_band(field.confidence),
            )
        )
    await session.commit()
    return len(selected)


async def _record_outcome(session: AsyncSession, family: str, correct: bool) -> QualityStat:
    stat = await session.scalar(select(QualityStat).where(QualityStat.family == family))
    if stat is None:
        stat = QualityStat(family=family)
        session.add(stat)
    stat.reviewed_count += 1
    stat.correct_count += int(correct)
    stat.accuracy = Decimal(stat.correct_count) / Decimal(stat.reviewed_count)
    return stat


async def complete_review(
    session: AsyncSession,
    review_id: UUID,
    reviewer: User,
    settings: Settings,
    *,
    corrected_value: str | None = None,
    corrected_numeric: Decimal | None = None,
    corrected_unit: str | None = None,
) -> tuple[QAReview, ExtractedField, tuple[str, ...]]:
    review = await session.get(QAReview, review_id)
    if review is None or review.status != "queued":
        raise ValueError("Queued review not found")
    candidate = await session.get(ExtractedField, review.extracted_field_id)
    if candidate is None:
        raise ValueError("Review candidate no longer exists")
    review.reviewer_user_id = reviewer.id
    if corrected_value is None:
        candidate.qa_status = "sampled_ok"
        reviewed = candidate
        review.status = "accepted"
        await _record_outcome(session, review.family, True)
    else:
        version = (
            int(
                (
                    await session.scalar(
                        select(func.max(ExtractedField.version)).where(
                            ExtractedField.filing_id == candidate.filing_id,
                            ExtractedField.field_key == candidate.field_key,
                        )
                    )
                )
                or 0
            )
            + 1
        )
        reviewed = ExtractedField(
            filing_id=candidate.filing_id,
            field_key=candidate.field_key,
            value_raw=corrected_value,
            value_num=corrected_numeric,
            value_date=candidate.value_date,
            unit=corrected_unit or candidate.unit,
            confidence=Decimal(1),
            method="human",
            source_page=candidate.source_page,
            source_span=candidate.source_span,
            qa_status="corrected",
            version=version,
        )
        session.add(reviewed)
        await session.flush()
        review.corrected_field_id = reviewed.id
        review.status = "corrected"
        await _record_outcome(session, review.family, False)
    decision = await update_pin_if_publishable(
        session, reviewed, settings, pinned_by_user_id=reviewer.id
    )
    await session.commit()
    return review, reviewed, decision.reasons
