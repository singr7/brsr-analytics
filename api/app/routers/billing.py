import asyncio
from datetime import UTC, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.access import CurrentOrg, CurrentUser
from api.app.core.config import Settings, get_settings
from api.app.db.session import get_db_session
from api.app.models import InvoiceRequest, Org
from api.app.schemas.billing import (
    InvoiceCreate,
    InvoiceSummary,
    LicenceChange,
    LicenceSummary,
)
from api.app.services.auth import send_email
from api.app.services.billing import RazorpayAdapter, invoice_plan_sheet
from api.app.services.plans import licence_state, public_plans
from api.app.services.track import persist_events

router = APIRouter(tags=["billing"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def licence_summary(org: Org) -> LicenceSummary:
    return LicenceSummary(
        org_id=org.id,
        tier=org.plan_tier,
        seats=org.seat_limit,
        starts_at=org.licence_starts_at,
        expires_at=org.licence_expires_at,
        grace_until=org.licence_grace_until,
        state=licence_state(org.licence_expires_at, org.licence_grace_until),
    )


@router.get("/api/plans")
async def plans() -> dict[str, object]:
    return public_plans()


@router.get("/api/billing/licence", response_model=LicenceSummary)
async def current_licence(context: CurrentOrg) -> LicenceSummary:
    return licence_summary(context.org)


@router.post(
    "/api/billing/invoice-requests",
    response_model=InvoiceSummary,
    status_code=status.HTTP_201_CREATED,
)
async def request_invoice(
    payload: InvoiceCreate,
    background: BackgroundTasks,
    context: CurrentOrg,
    user: CurrentUser,
    session: SessionDep,
    settings: SettingsDep,
) -> InvoiceSummary:
    if context.membership.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Owner role required")
    if settings.razorpay_enabled:
        try:
            RazorpayAdapter().create_payment_link()
        except NotImplementedError as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Razorpay adapter is enabled but not configured; no charge was attempted",
            ) from exc
    invoice = InvoiceRequest(
        org_id=context.org.id,
        requested_by_user_id=user.id,
        requested_tier=payload.tier,
        seats=payload.seats,
        term_months=payload.term_months,
        billing_email=str(payload.billing_email),
        status="requested",
    )
    session.add(invoice)
    await persist_events(
        session,
        [
            {
                "name": "invoice_requested",
                "session_id": user.id,
                "properties": {"org_id": str(context.org.id), "tier": payload.tier},
            }
        ],
        anon_id=None,
        user_id=user.id,
    )
    await session.commit()
    background.add_task(
        asyncio.to_thread,
        send_email,
        settings,
        settings.billing_ops_email,
        f"BRSR Lens invoice request · {context.org.name}",
        invoice_plan_sheet(
            payload.tier, payload.seats, payload.term_months, str(payload.billing_email)
        ),
    )
    return InvoiceSummary(id=invoice.id, status=invoice.status)


@router.put("/api/admin/orgs/{org_id}/licence", response_model=LicenceSummary)
async def set_licence(
    org_id: UUID,
    payload: LicenceChange,
    user: CurrentUser,
    session: SessionDep,
) -> LicenceSummary:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Platform administrator required")
    if payload.expires_at <= payload.starts_at:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Expiry must follow start")
    org = await session.get(Org, org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organisation not found")
    previous = org.plan_tier
    org.plan_tier = payload.tier
    org.seat_limit = payload.seats
    org.licence_starts_at = payload.starts_at.astimezone(UTC)
    org.licence_expires_at = payload.expires_at.astimezone(UTC)
    org.licence_grace_until = org.licence_expires_at + timedelta(days=payload.grace_days)
    await persist_events(
        session,
        [
            {
                "name": "plan_changed",
                "session_id": user.id,
                "properties": {
                    "org_id": str(org.id),
                    "from": previous,
                    "to": payload.tier,
                    "seats": payload.seats,
                },
            }
        ],
        anon_id=None,
        user_id=user.id,
    )
    if payload.tier == "pro":
        await persist_events(
            session,
            [
                {
                    "name": "plan_changed_to_pro",
                    "session_id": user.id,
                    "properties": {"org_id": str(org.id), "tier": "pro"},
                }
            ],
            anon_id=None,
            user_id=user.id,
        )
    await session.commit()
    return licence_summary(org)
