from datetime import timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.access import CurrentUser, optional_user
from api.app.core.config import Settings, get_settings
from api.app.db.session import get_db_session
from api.app.models import Event
from api.app.schemas.auth import EventBatch, MessageResponse
from api.app.schemas.engagement import PrivacyPreference
from api.app.services.rate_limit import public_rate_limit
from api.app.services.track import persist_events

router = APIRouter(prefix="/api", tags=["tracking"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@router.post("/events", status_code=status.HTTP_202_ACCEPTED)
async def ingest_events(
    payload: EventBatch,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[object | None, Depends(optional_user)],
    anon_id: Annotated[UUID | None, Cookie()] = None,
    analytics_opt_out: Annotated[str | None, Cookie()] = None,
) -> dict[str, int]:
    await public_rate_limit(request, settings)
    if analytics_opt_out == "1":
        return {"accepted": 0}
    anonymous_id = anon_id or uuid4()
    try:
        accepted = await persist_events(
            session,
            [event.model_dump() for event in payload.events],
            anon_id=anonymous_id,
            user_id=getattr(user, "id", None),
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    await session.commit()
    if anon_id is None:
        response.set_cookie(
            "anon_id",
            str(anonymous_id),
            max_age=int(timedelta(days=365).total_seconds()),
            httponly=False,
            samesite="lax",
            secure=settings.app_env == "production",
        )
    return {"accepted": accepted}


@router.get("/privacy/export")
async def privacy_export(user: CurrentUser, session: SessionDep) -> dict[str, object]:
    events = (
        await session.execute(select(Event).where(Event.user_id == user.id).order_by(Event.ts))
    ).scalars()
    return {
        "user_id": str(user.id),
        "events": [
            {
                "name": event.name,
                "properties": event.props_json,
                "occurred_at": event.ts.isoformat(),
            }
            for event in events
        ],
    }


@router.delete("/privacy/delete", response_model=MessageResponse)
async def privacy_delete(user: CurrentUser, session: SessionDep) -> MessageResponse:
    result = await session.execute(delete(Event).where(Event.user_id == user.id))
    await session.commit()
    count = int(result.rowcount)  # type: ignore[attr-defined]
    return MessageResponse(message=f"Deleted {count} events")


@router.put("/privacy/preference", response_model=PrivacyPreference)
async def privacy_preference(
    payload: PrivacyPreference,
    response: Response,
    user: CurrentUser,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> PrivacyPreference:
    user.analytics_opt_out = not payload.analytics_enabled
    if user.analytics_opt_out:
        await session.execute(delete(Event).where(Event.user_id == user.id))
    await session.commit()
    response.set_cookie(
        "analytics_opt_out",
        "0" if payload.analytics_enabled else "1",
        max_age=int(timedelta(days=365).total_seconds()),
        httponly=False,
        samesite="lax",
        secure=settings.app_env == "production",
    )
    return payload
