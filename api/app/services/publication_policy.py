from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.config import Settings
from api.app.models import ExtractedField, FieldVersionPin, QualityStat


def field_family(field_key: str) -> str:
    parts = field_key.split(".")
    return ".".join(parts[:2]) if len(parts) > 1 else field_key


@dataclass(frozen=True, slots=True)
class PublishDecision:
    allowed: bool
    reasons: tuple[str, ...]


def evaluate_publishability(
    field: ExtractedField,
    family_accuracy: Decimal | None,
    *,
    confidence_threshold: Decimal,
    accuracy_target: Decimal,
) -> PublishDecision:
    reasons: list[str] = []
    if field.qa_status not in {"sampled_ok", "corrected"}:
        reasons.append("qa_not_passed")
    if field.confidence is None or field.confidence < confidence_threshold:
        reasons.append("confidence_below_threshold")
    if family_accuracy is None or family_accuracy < accuracy_target:
        reasons.append("family_accuracy_below_target")
    return PublishDecision(not reasons, tuple(reasons))


async def update_pin_if_publishable(
    session: AsyncSession,
    field: ExtractedField,
    settings: Settings,
    *,
    pinned_by_user_id: UUID | None = None,
) -> PublishDecision:
    stat = await session.scalar(
        select(QualityStat).where(QualityStat.family == field_family(field.field_key))
    )
    decision = evaluate_publishability(
        field,
        stat.accuracy if stat else None,
        confidence_threshold=Decimal(str(settings.publish_threshold)),
        accuracy_target=Decimal(str(settings.publish_family_accuracy_target)),
    )
    if not decision.allowed:
        return decision
    pin = await session.scalar(
        select(FieldVersionPin).where(
            FieldVersionPin.filing_id == field.filing_id,
            FieldVersionPin.field_key == field.field_key,
        )
    )
    if pin is None:
        pin = FieldVersionPin(
            filing_id=field.filing_id,
            field_key=field.field_key,
            extracted_field_id=field.id,
            pinned_by_user_id=pinned_by_user_id,
        )
        session.add(pin)
    else:
        pin.extracted_field_id = field.id
        pin.pinned_by_user_id = pinned_by_user_id
    return decision
