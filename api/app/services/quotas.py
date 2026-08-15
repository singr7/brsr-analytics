from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from fastapi import HTTPException, status

from api.app.services.plans import plan

QuotaName = Literal[
    "nlq_per_day",
    "studio_tokens_per_month",
    "exports_per_month",
    "api_queries_per_minute",
]


@dataclass(frozen=True, slots=True)
class QuotaStatus:
    name: QuotaName
    used: int
    limit: int

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)

    @property
    def warning(self) -> bool:
        return self.limit > 0 and self.used / self.limit >= 0.8


def quota_limit(tier: str, name: QuotaName) -> int:
    return int(plan(tier)["quotas"].get(name, 0))


def quota_status(tier: str, name: QuotaName, used: int) -> QuotaStatus:
    return QuotaStatus(name=name, used=used, limit=quota_limit(tier, name))


def enforce_quota(tier: str, name: QuotaName, used: int, increment: int = 1) -> QuotaStatus:
    result = quota_status(tier, name, used + increment)
    if result.limit <= 0 or result.used > result.limit:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "quota_exceeded", "quota": name, "limit": result.limit},
        )
    return result


def period_key(name: QuotaName, now: datetime | None = None) -> tuple[str, int]:
    current = now or datetime.now(UTC)
    if name == "api_queries_per_minute":
        return current.strftime("%Y-%m-%dT%H:%M"), 120
    if name == "nlq_per_day":
        return current.strftime("%Y-%m-%d"), 172_800
    return current.strftime("%Y-%m"), 2_678_400


async def consume_redis_quota(
    redis_client: object,
    *,
    tier: str,
    identity: str,
    name: QuotaName,
    increment: int = 1,
) -> QuotaStatus:
    period, ttl = period_key(name)
    key = f"quota:{name}:{tier}:{identity}:{period}"
    used = int(await redis_client.incrby(key, increment))  # type: ignore[attr-defined]
    if used == increment:
        await redis_client.expire(key, ttl)  # type: ignore[attr-defined]
    return enforce_quota(tier, name, used - increment, increment)
