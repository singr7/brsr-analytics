from typing import Protocol

from fastapi import HTTPException, Request, status

from api.app.core.access import client_ip
from api.app.core.config import Settings


class RedisCounter(Protocol):
    async def incr(self, key: str) -> int: ...

    async def expire(self, key: str, seconds: int) -> object: ...


async def enforce_rate_limit(
    request: Request, settings: Settings, scope: str, identity: str, limit: int
) -> None:
    client: RedisCounter | None = getattr(request.app.state, "redis", None)
    if client is None:
        return
    key = f"rate:{scope}:{identity}"
    try:
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, 60)
    except Exception:
        return  # Analytics and public reads remain available during Redis degradation.
    if count > limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Rate limit exceeded")


async def public_rate_limit(request: Request, settings: Settings) -> None:
    await enforce_rate_limit(
        request,
        settings,
        scope="public",
        identity=client_ip(request),
        limit=settings.public_rate_limit_per_minute,
    )
