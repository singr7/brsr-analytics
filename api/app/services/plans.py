from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

import yaml


class QuotaConfig(TypedDict, total=False):
    nlq_per_day: int
    studio_tokens_per_month: int
    exports_per_month: int
    api_queries_per_minute: int


class PlanConfig(TypedDict):
    name: str
    price_label: str
    description: str
    seats: int
    quotas: QuotaConfig
    features: list[str]
    cta: str


class PlansConfig(TypedDict):
    version: int
    currency: str
    licence_terms_url: str
    tiers: dict[str, PlanConfig]
    faq: list[dict[str, str]]


@lru_cache
def load_plans(path: str | Path = "plans.yaml") -> PlansConfig:
    payload = yaml.safe_load(Path(path).read_text())
    if not isinstance(payload, dict) or not isinstance(payload.get("tiers"), dict):
        raise ValueError("plans.yaml must define tiers")
    return cast(PlansConfig, payload)


def plan(tier: str) -> PlanConfig:
    try:
        return load_plans()["tiers"][tier]
    except KeyError as exc:
        raise ValueError(f"Unknown plan tier: {tier}") from exc


def licence_state(
    expires_at: datetime | None,
    grace_until: datetime | None,
    *,
    now: datetime | None = None,
) -> Literal["active", "grace", "read_only"]:
    current = now or datetime.now(UTC)
    if expires_at is None or current <= expires_at:
        return "active"
    if grace_until is not None and current <= grace_until:
        return "grace"
    return "read_only"


def public_plans() -> dict[str, Any]:
    config = load_plans()
    return {
        "version": config["version"],
        "currency": config["currency"],
        "licence_terms_url": config["licence_terms_url"],
        "tiers": config["tiers"],
        "faq": config["faq"],
    }
