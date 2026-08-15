import asyncio
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.access import CurrentUser
from api.app.core.config import Settings, get_settings
from api.app.db.session import get_db_session
from api.app.models import EmailVerification, Membership, Org, RefreshToken, User
from api.app.schemas.auth import (
    LoginRequest,
    MeResponse,
    MessageResponse,
    OrgSummary,
    RefreshRequest,
    SignupRequest,
    SignupResponse,
    TokenPair,
    VerifyRequest,
)
from api.app.services.auth import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_opaque_token,
    hash_password,
    opaque_token,
    send_email,
    verify_password,
)
from api.app.services.plans import licence_state
from api.app.services.track import merge_anonymous_history, persist_events

router = APIRouter(prefix="/api/auth", tags=["auth"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def _issue_pair(
    session: AsyncSession, settings: Settings, user_id: UUID, family_id: UUID | None = None
) -> tuple[TokenPair, RefreshToken]:
    access, expires_in = create_access_token(settings, user_id)
    refresh, jti, family, refresh_expiry = create_refresh_token(settings, user_id, family_id)
    row = RefreshToken(
        jti=jti,
        family_id=family,
        user_id=user_id,
        expires_at=refresh_expiry,
        revoked_at=None,
        replaced_by_jti=None,
        reuse_detected=False,
    )
    session.add(row)
    return TokenPair(access_token=access, refresh_token=refresh, expires_in=expires_in), row


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    payload: SignupRequest,
    background: BackgroundTasks,
    session: SessionDep,
    settings: SettingsDep,
) -> SignupResponse:
    email = str(payload.email).lower()
    if await session.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name.strip(),
        plan_tier="explore",
        email_verified_at=None,
    )
    session.add(user)
    await session.flush()
    raw_token = opaque_token()
    session.add(
        EmailVerification(
            user_id=user.id,
            token_hash=hash_opaque_token(raw_token),
            expires_at=datetime.now(UTC) + timedelta(hours=settings.verification_token_hours),
            used_at=None,
        )
    )
    await persist_events(
        session,
        [{"name": "signup_completed", "session_id": user.id, "properties": {}}],
        anon_id=None,
        user_id=user.id,
    )
    await session.commit()
    verify_url = f"{settings.frontend_url}/?verify={raw_token}"
    background.add_task(
        asyncio.to_thread,
        send_email,
        settings,
        email,
        "Verify your BRSR Lens email",
        f"Verify your email: {verify_url}",
    )
    return SignupResponse(
        user_id=user.id,
        verification_token=raw_token if settings.auth_expose_verification_token else None,
    )


@router.post("/verify", response_model=MessageResponse)
async def verify_email(payload: VerifyRequest, session: SessionDep) -> MessageResponse:
    now = datetime.now(UTC)
    row = await session.scalar(
        select(EmailVerification).where(
            EmailVerification.token_hash == hash_opaque_token(payload.token),
            EmailVerification.used_at.is_(None),
            EmailVerification.expires_at > now,
        )
    )
    if row is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Verification token is invalid or expired")
    user = await session.get(User, row.user_id)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Verification token is invalid")
    user.email_verified_at = now
    row.used_at = now
    await session.commit()
    return MessageResponse(message="Email verified")


@router.post("/login", response_model=TokenPair)
async def login(
    payload: LoginRequest,
    session: SessionDep,
    settings: SettingsDep,
    anon_id: Annotated[UUID | None, Cookie()] = None,
) -> TokenPair:
    user = await session.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is None or not verify_password(user.password_hash, payload.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if user.email_verified_at is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Email verification required")
    pair, _ = await _issue_pair(session, settings, user.id)
    await merge_anonymous_history(session, anon_id, user.id)
    await persist_events(
        session,
        [{"name": "login_completed", "session_id": user.id, "properties": {}}],
        anon_id=anon_id,
        user_id=user.id,
    )
    await session.commit()
    return pair


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, session: SessionDep, settings: SettingsDep) -> TokenPair:
    try:
        claims = decode_token(settings, payload.refresh_token, "refresh")
        jti = UUID(str(claims["jti"]))
        user_id = UUID(str(claims["sub"]))
        family_id = UUID(str(claims["family"]))
    except (TokenError, KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token") from exc
    row = await session.scalar(
        select(RefreshToken).where(RefreshToken.jti == jti).with_for_update()
    )
    now = datetime.now(UTC)
    if row is None or row.user_id != user_id or row.expires_at <= now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    if row.revoked_at is not None:
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id)
            .values(revoked_at=now, reuse_detected=True)
        )
        await session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token reuse detected")
    pair, replacement = await _issue_pair(session, settings, user_id, family_id)
    row.revoked_at = now
    row.replaced_by_jti = replacement.jti
    await session.commit()
    return pair


@router.get("/me", response_model=MeResponse)
async def me(user: CurrentUser, session: SessionDep) -> MeResponse:
    rows = (
        await session.execute(
            select(Org, Membership)
            .join(Membership, Membership.org_id == Org.id)
            .where(Membership.user_id == user.id)
            .order_by(Org.name)
        )
    ).all()
    return MeResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        email_verified_at=user.email_verified_at,
        plan_tier=user.plan_tier,
        is_admin=user.is_admin,
        orgs=[
            OrgSummary(
                id=org.id,
                name=org.name,
                slug=org.slug,
                role=membership.role,
                plan_tier=org.plan_tier,
                licence_state=licence_state(org.licence_expires_at, org.licence_grace_until),
                seat_limit=org.seat_limit,
                licence_expires_at=org.licence_expires_at,
            )
            for org, membership in rows
        ],
    )
