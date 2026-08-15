from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.config import Settings, get_settings
from api.app.db.session import get_db_session
from api.app.models import Membership, Org, User
from api.app.services.auth import TokenError, decode_token
from api.app.services.plans import licence_state

bearer = HTTPBearer(auto_error=False)
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


async def optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> User | None:
    if credentials is None:
        return None
    try:
        payload = decode_token(settings, credentials.credentials, "access")
        user_id = UUID(str(payload["sub"]))
    except (TokenError, ValueError, KeyError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid access token") from exc
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")
    return user


async def current_user(user: Annotated[User | None, Depends(optional_user)]) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


@dataclass(frozen=True, slots=True)
class OrgContext:
    org: Org
    membership: Membership


async def current_org(
    user: CurrentUser,
    session: SessionDep,
    x_org_id: Annotated[UUID | None, Header()] = None,
) -> OrgContext:
    if x_org_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "X-Org-ID header is required")
    row = (
        await session.execute(
            select(Org, Membership)
            .join(Membership, Membership.org_id == Org.id)
            .where(Org.id == x_org_id, Membership.user_id == user.id)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Organisation access denied")
    return OrgContext(org=row[0], membership=row[1])


CurrentOrg = Annotated[OrgContext, Depends(current_org)]


def require_role(*roles: str) -> object:
    async def dependency(context: CurrentOrg) -> OrgContext:
        if context.membership.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Organisation role denied")
        return context

    return Depends(dependency)


def require_plan(*tiers: str) -> object:
    async def dependency(context: CurrentOrg) -> OrgContext:
        if context.org.plan_tier not in tiers:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail={"code": "plan_required", "allowed_tiers": tiers},
            )
        return context

    return Depends(dependency)


def ensure_writable(context: OrgContext) -> None:
    if (
        licence_state(
            getattr(context.org, "licence_expires_at", None),
            getattr(context.org, "licence_grace_until", None),
        )
        == "read_only"
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={
                "code": "licence_read_only",
                "message": "Licence expired; reads remain available",
            },
        )


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", maxsplit=1)[0].strip()
    return request.client.host if request.client else "unknown"
