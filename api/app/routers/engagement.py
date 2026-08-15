from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select

from api.app.core.access import CurrentUser, SessionDep
from api.app.core.config import Settings, get_settings
from api.app.models import Company, DeepdiveRequest, Lead, Membership
from api.app.routers.acquisition import require_platform_admin
from api.app.schemas.engagement import (
    AnalyticsResponse,
    CompanyOption,
    DeepdiveCreate,
    DeepdiveItem,
    DeepdiveStatusUpdate,
    LeadItem,
    LeadOutcomeUpdate,
    LeadQualityResponse,
    LeadQualitySignal,
    LeadSignal,
)
from api.app.services.engagement import lead_quality, load_analytics
from api.app.services.leads import route_lead, score_user_lead
from api.app.services.track import persist_events

router = APIRouter(prefix="/api", tags=["engagement"])
admin_router = APIRouter(
    prefix="/api/admin",
    tags=["engagement-admin"],
    dependencies=[Depends(require_platform_admin)],
)


@router.get("/companies/options", response_model=list[CompanyOption])
async def company_options(session: SessionDep) -> list[CompanyOption]:
    rows = (await session.scalars(select(Company).order_by(Company.name))).all()
    return [
        CompanyOption(id=company.id, name=company.name, sector=company.sector)
        for company in rows
    ]


def _deepdive_item(request: DeepdiveRequest) -> DeepdiveItem:
    context = request.context_json
    return DeepdiveItem(
        id=request.id,
        user_id=request.user_id,
        org_id=request.org_id,
        company_ids=[UUID(str(item)) for item in cast(list[object], context["company_ids"])],
        question=request.request_text,
        timeframe=str(context["timeframe"]),
        budget_band=str(context["budget_band"]),
        contact_email=str(context["contact_email"]),
        status=request.status,
        created_at=request.created_at,
    )


@router.post(
    "/deepdives", response_model=DeepdiveItem, status_code=status.HTTP_201_CREATED
)
async def create_deepdive(
    payload: DeepdiveCreate,
    user: CurrentUser,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    x_org_id: Annotated[UUID | None, Header()] = None,
) -> DeepdiveItem:
    if x_org_id is not None and not await session.scalar(
        select(Membership.id).where(
            Membership.org_id == x_org_id, Membership.user_id == user.id
        )
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Organisation access denied")
    found = set(
        await session.scalars(select(Company.id).where(Company.id.in_(payload.company_ids)))
    )
    if found != set(payload.company_ids):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown company in request")
    request = DeepdiveRequest(
        user_id=user.id,
        org_id=x_org_id,
        company_id=payload.company_ids[0],
        request_text=payload.question.strip(),
        context_json={
            "company_ids": [str(item) for item in payload.company_ids],
            "timeframe": payload.timeframe,
            "budget_band": payload.budget_band,
            "contact_email": str(payload.contact_email),
        },
        status="new",
    )
    session.add(request)
    await session.flush()
    await persist_events(
        session,
        [
            {
                "name": "deepdive_requested",
                "session_id": user.id,
                "properties": {
                    "request_id": str(request.id),
                    "org_id": str(x_org_id) if x_org_id else None,
                    "company_count": len(payload.company_ids),
                    "budget_band": payload.budget_band,
                },
            }
        ],
        anon_id=None,
        user_id=user.id,
    )
    lead = await score_user_lead(session, user)
    if lead is None and not user.analytics_opt_out:
        lead = Lead(
            user_id=user.id,
            org_id=x_org_id,
            score=Decimal(50),
            signals_json={"timeline": [], "instant_route": True},
            status="new",
        )
        session.add(lead)
        await session.flush()
    if lead is not None:
        await route_lead(session, settings, lead, force=True)
    await session.commit()
    await session.refresh(request)
    return _deepdive_item(request)


@admin_router.get("/analytics", response_model=AnalyticsResponse)
async def analytics(
    session: SessionDep, days: Annotated[int, Query(ge=1, le=366)] = 30
) -> AnalyticsResponse:
    return AnalyticsResponse.model_validate(await load_analytics(session, days=days))


def _lead_item(lead: Lead) -> LeadItem:
    timeline = lead.signals_json.get("timeline", [])
    return LeadItem(
        id=lead.id,
        user_id=lead.user_id,
        org_id=lead.org_id,
        score=float(lead.score),
        signals=[LeadSignal.model_validate(item) for item in timeline]
        if isinstance(timeline, list)
        else [],
        status=lead.status,
        routed_at=lead.routed_at,
        outcome=lead.outcome,
        outcome_note=lead.outcome_note,
    )


@admin_router.get("/leads", response_model=list[LeadItem])
async def list_leads(session: SessionDep) -> list[LeadItem]:
    rows = (await session.scalars(select(Lead).order_by(Lead.score.desc()))).all()
    return [_lead_item(lead) for lead in rows]


@admin_router.patch("/leads/{lead_id}/outcome", response_model=LeadItem)
async def update_lead_outcome(
    lead_id: UUID, payload: LeadOutcomeUpdate, session: SessionDep
) -> LeadItem:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found")
    lead.outcome = payload.outcome
    lead.outcome_note = payload.note
    if payload.outcome in {"won", "lost", "not_a_fit"}:
        lead.status = "closed"
    elif payload.outcome in {"qualified", "meeting", "proposal"}:
        lead.status = "qualified"
    await session.commit()
    return _lead_item(lead)


@admin_router.get("/leads/quality", response_model=LeadQualityResponse)
async def quality(session: SessionDep) -> LeadQualityResponse:
    signals = await lead_quality(session)
    return LeadQualityResponse(
        generated_at=datetime.now(UTC),
        by_signal=[LeadQualitySignal.model_validate(item) for item in signals],
    )


@admin_router.get("/deepdives", response_model=list[DeepdiveItem])
async def list_deepdives(session: SessionDep) -> list[DeepdiveItem]:
    rows = (
        await session.scalars(select(DeepdiveRequest).order_by(DeepdiveRequest.created_at.desc()))
    ).all()
    return [_deepdive_item(request) for request in rows]


@admin_router.patch("/deepdives/{request_id}", response_model=DeepdiveItem)
async def update_deepdive(
    request_id: UUID, payload: DeepdiveStatusUpdate, session: SessionDep
) -> DeepdiveItem:
    request = await session.get(DeepdiveRequest, request_id)
    if request is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Deep-dive request not found")
    transitions = {"new": "scoped", "scoped": "quoted", "quoted": "delivered"}
    if payload.status != request.status and transitions.get(request.status) != payload.status:
        raise HTTPException(status.HTTP_409_CONFLICT, "Deep-dive status must advance one step")
    request.status = payload.status
    await session.commit()
    return _deepdive_item(request)
