import asyncio
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.access import CurrentOrg, CurrentUser
from api.app.core.config import Settings, get_settings
from api.app.db.session import get_db_session
from api.app.models import Membership, Org, OrgInvite, Plan
from api.app.schemas.auth import (
    AcceptInviteRequest,
    CreateOrgRequest,
    InviteRequest,
    InviteResponse,
    MessageResponse,
    OrgSummary,
    PlanChangeRequest,
)
from api.app.services.auth import hash_opaque_token, opaque_token, send_email
from api.app.services.rate_limit import enforce_rate_limit
from api.app.services.track import persist_events

router = APIRouter(prefix="/api/orgs", tags=["organisations"])
admin_router = APIRouter(prefix="/api/admin", tags=["admin"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.post("", response_model=OrgSummary, status_code=status.HTTP_201_CREATED)
async def create_org(
    payload: CreateOrgRequest, user: CurrentUser, session: SessionDep
) -> OrgSummary:
    if await session.scalar(select(Org.id).where(Org.slug == payload.slug)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Organisation slug already exists")
    org = Org(name=payload.name.strip(), slug=payload.slug, plan_tier="explore")
    session.add(org)
    await session.flush()
    membership = Membership(org_id=org.id, user_id=user.id, role="owner")
    session.add(membership)
    await persist_events(
        session,
        [{"name": "org_created", "session_id": user.id, "properties": {"org_id": str(org.id)}}],
        anon_id=None,
        user_id=user.id,
    )
    await session.commit()
    return OrgSummary(id=org.id, name=org.name, slug=org.slug, role="owner", plan_tier="explore")


@router.post("/invites", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
async def invite_member(
    payload: InviteRequest,
    background: BackgroundTasks,
    request: Request,
    context: CurrentOrg,
    session: SessionDep,
    settings: SettingsDep,
) -> InviteResponse:
    if context.membership.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Owner role required")
    await enforce_rate_limit(
        request,
        settings,
        scope="org",
        identity=str(context.org.id),
        limit=settings.org_rate_limit_per_minute,
    )
    token = opaque_token()
    invite = OrgInvite(
        org_id=context.org.id,
        email=str(payload.email).lower(),
        role=payload.role,
        token_hash=hash_opaque_token(token),
        expires_at=datetime.now(UTC) + timedelta(days=7),
        accepted_at=None,
    )
    session.add(invite)
    await session.commit()
    background.add_task(
        asyncio.to_thread,
        send_email,
        settings,
        invite.email,
        f"Join {context.org.name} on BRSR Lens",
        f"Accept your invite: {settings.frontend_url}/?invite={token}",
    )
    return InviteResponse(
        invite_id=invite.id,
        invite_token=token if settings.auth_expose_verification_token else None,
    )


@router.post("/invites/accept", response_model=MessageResponse)
async def accept_invite(
    payload: AcceptInviteRequest, user: CurrentUser, session: SessionDep
) -> MessageResponse:
    now = datetime.now(UTC)
    invite = await session.scalar(
        select(OrgInvite).where(
            OrgInvite.token_hash == hash_opaque_token(payload.token),
            OrgInvite.accepted_at.is_(None),
            OrgInvite.expires_at > now,
        )
    )
    if invite is None or invite.email != user.email.lower():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invite is invalid or expired")
    existing = await session.scalar(
        select(Membership).where(Membership.org_id == invite.org_id, Membership.user_id == user.id)
    )
    if existing is None:
        session.add(Membership(org_id=invite.org_id, user_id=user.id, role=invite.role))
    invite.accepted_at = now
    await session.commit()
    return MessageResponse(message="Organisation invite accepted")


@admin_router.patch("/orgs/{org_id}/plan", response_model=OrgSummary)
async def change_plan(
    org_id: UUID,
    payload: PlanChangeRequest,
    user: CurrentUser,
    session: SessionDep,
) -> OrgSummary:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Platform administrator required")
    org = await session.get(Org, org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organisation not found")
    if await session.get(Plan, payload.tier) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown plan")
    org.plan_tier = payload.tier
    await session.commit()
    return OrgSummary(
        id=org.id,
        name=org.name,
        slug=org.slug,
        role="platform_admin",
        plan_tier=org.plan_tier,
    )
