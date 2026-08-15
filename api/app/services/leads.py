from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol, cast

import httpx
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.config import Settings
from api.app.models import Event, Lead, Membership, Org, User
from api.app.services.auth import send_email

REPO_ROOT = Path(__file__).resolve().parents[3]
POSITIVE_OUTCOMES = frozenset({"qualified", "meeting", "proposal", "won"})


@dataclass(frozen=True, slots=True)
class EventFact:
    name: str
    occurred_at: datetime
    properties: dict[str, object]


@dataclass(frozen=True, slots=True)
class ScoredSignal:
    key: str
    label: str
    occurred_at: datetime
    points: int
    properties: dict[str, object]


@dataclass(frozen=True, slots=True)
class LeadScore:
    score: int
    signals: tuple[ScoredSignal, ...]
    instant_route: bool


def load_lead_rules(path: Path | None = None) -> dict[str, Any]:
    document = yaml.safe_load((path or REPO_ROOT / "leads.yaml").read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("signals"), dict):
        raise ValueError("leads.yaml must define a signals mapping")
    return cast(dict[str, Any], document)


def _matches(event: EventFact, key: str, rule: dict[str, Any]) -> bool:
    if event.name != str(rule.get("event", key)):
        return False
    contains = rule.get("property_contains")
    if not isinstance(contains, dict):
        return True
    for property_name, terms in contains.items():
        value = str(event.properties.get(str(property_name), "")).lower()
        if not any(str(term).lower() in value for term in cast(list[object], terms)):
            return False
    return True


def score_events(
    events: list[EventFact], rules: dict[str, Any] | None = None, now: datetime | None = None
) -> LeadScore:
    config = rules or load_lead_rules()
    current = now or datetime.now(UTC)
    cutoff = current - timedelta(days=int(config["window_days"]))
    signals: list[ScoredSignal] = []
    instant = False
    for key, raw_rule in cast(dict[str, Any], config["signals"]).items():
        rule = cast(dict[str, Any], raw_rule)
        matched = sorted(
            (
                event
                for event in events
                if event.occurred_at >= cutoff and _matches(event, key, rule)
            ),
            key=lambda item: item.occurred_at,
            reverse=True,
        )[: int(rule.get("max_occurrences", 1))]
        points = int(rule["weight"])
        for event in matched:
            signals.append(
                ScoredSignal(
                    key=key,
                    label=str(rule["label"]),
                    occurred_at=event.occurred_at,
                    points=points,
                    properties=event.properties,
                )
            )
        instant = instant or bool(matched and rule.get("instant_route", False))
    signals.sort(key=lambda item: item.occurred_at)
    return LeadScore(sum(signal.points for signal in signals), tuple(signals), instant)


def signals_document(score: LeadScore) -> dict[str, object]:
    return {
        "timeline": [
            {
                "key": signal.key,
                "label": signal.label,
                "occurred_at": signal.occurred_at.isoformat(),
                "points": signal.points,
                "properties": signal.properties,
            }
            for signal in score.signals
        ],
        "instant_route": score.instant_route,
    }


def suggested_opening(org_name: str | None, signals: tuple[ScoredSignal, ...]) -> str:
    company = next(
        (
            str(signal.properties.get("company"))
            for signal in reversed(signals)
            if signal.properties.get("company")
        ),
        None,
    )
    focus = next((signal.label.lower() for signal in reversed(signals)), "BRSR priorities")
    subject = org_name or "your team"
    company_phrase = f" for {company}" if company else ""
    return (
        f"Ask how {subject} is approaching {focus}{company_phrase}, "
        "and offer a focused working session."
    )


def context_card(
    lead: Lead, user: User | None, org: Org | None, signals: tuple[ScoredSignal, ...]
) -> str:
    who = f"{user.display_name} <{user.email}>" if user else "An authenticated organisation contact"
    timeline = "\n".join(
        f"- {signal.occurred_at:%d %b}: {signal.label} (+{signal.points})"
        for signal in signals
    )
    return (
        "A BRSR Lens user may benefit from a timely, useful conversation.\n\n"
        f"Who: {who}\nOrganisation: {org.name if org else 'Personal workspace'}\n"
        f"Engagement score: {lead.score}\n\nWhat they have been working on:\n{timeline}\n\n"
        f"Suggested opening:\n{suggested_opening(org.name if org else None, signals)}\n\n"
        "Use this context to be relevant, not intrusive. Do not mention tracking or the score."
    )


def webhook_body(
    lead: Lead, user: User | None, org: Org | None, signals: tuple[ScoredSignal, ...]
) -> bytes:
    payload = {
        "version": "2026-08-15",
        "event": "lead.ready",
        "lead": {
            "id": str(lead.id),
            "score": float(lead.score),
            "user": {"id": str(user.id), "email": user.email} if user else None,
            "organisation": {"id": str(org.id), "name": org.name} if org else None,
            "signals": [
                {
                    "key": signal.key,
                    "label": signal.label,
                    "occurred_at": signal.occurred_at.isoformat(),
                    "points": signal.points,
                    "properties": signal.properties,
                }
                for signal in signals
            ],
            "suggested_opening": suggested_opening(org.name if org else None, signals),
        },
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def webhook_signature(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def routing_eligible(
    *,
    score: float,
    threshold: int,
    instant: bool,
    opted_out: bool,
    already_routed: bool,
    organisation_recently_routed: bool,
) -> bool:
    return (
        not opted_out
        and not already_routed
        and not organisation_recently_routed
        and (instant or score >= threshold)
    )


class AsyncPoster(Protocol):
    async def post(
        self, url: str, *, content: bytes, headers: dict[str, str]
    ) -> httpx.Response: ...


async def post_webhook(
    client: AsyncPoster, url: str, secret: str, body: bytes, attempts: int = 3
) -> int:
    headers = {
        "Content-Type": "application/json",
        "X-BRSRLens-Signature": webhook_signature(secret, body),
    }
    last_status = 0
    for attempt in range(attempts):
        try:
            response = await client.post(url, content=body, headers=headers)
            last_status = response.status_code
            if 200 <= response.status_code < 300:
                return response.status_code
        except httpx.HTTPError:
            last_status = 0
        if attempt + 1 < attempts:
            await asyncio.sleep(2**attempt)
    raise RuntimeError(f"Lead webhook failed after {attempts} attempts (status={last_status})")


def decode_signals(lead: Lead) -> tuple[ScoredSignal, ...]:
    raw = lead.signals_json.get("timeline", [])
    if not isinstance(raw, list):
        return ()
    return tuple(
        ScoredSignal(
            key=str(item["key"]),
            label=str(item["label"]),
            occurred_at=datetime.fromisoformat(str(item["occurred_at"])),
            points=int(item["points"]),
            properties=cast(dict[str, object], item.get("properties", {})),
        )
        for item in raw
        if isinstance(item, dict)
    )


async def score_user_lead(
    session: AsyncSession, user: User, now: datetime | None = None
) -> Lead | None:
    if user.analytics_opt_out:
        return None
    config = load_lead_rules()
    current = now or datetime.now(UTC)
    cutoff = current - timedelta(days=int(config["window_days"]))
    rows = (
        await session.scalars(
            select(Event)
            .where(Event.user_id == user.id, Event.ts >= cutoff)
            .order_by(Event.ts)
        )
    ).all()
    score = score_events(
        [EventFact(row.name, row.ts, row.props_json) for row in rows], config, current
    )
    if not score.signals:
        return None
    membership = await session.scalar(
        select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at)
    )
    org_id = membership.org_id if membership else None
    existing = await session.scalar(
        select(Lead).where(Lead.user_id == user.id, Lead.status.in_(("new", "routed")))
    )
    lead = existing or Lead(user_id=user.id, org_id=org_id, signals_json={})
    lead.score = Decimal(score.score)
    lead.signals_json = signals_document(score)
    if existing is None:
        session.add(lead)
    await session.flush()
    return lead


async def route_lead(
    session: AsyncSession, settings: Settings, lead: Lead, force: bool = False
) -> bool:
    user = await session.get(User, lead.user_id) if lead.user_id else None
    config = load_lead_rules()
    instant = bool(lead.signals_json.get("instant_route"))
    cutoff = datetime.now(UTC) - timedelta(days=int(config["route_suppression_days"]))
    recently_routed = None
    if lead.org_id:
        recently_routed = await session.scalar(
            select(Lead.id).where(
                Lead.org_id == lead.org_id,
                Lead.id != lead.id,
                Lead.routed_at.is_not(None),
                Lead.routed_at >= cutoff,
            )
        )
    if not routing_eligible(
        score=float(lead.score),
        threshold=0 if force else int(config["route_threshold"]),
        instant=instant,
        opted_out=bool(user and user.analytics_opt_out),
        already_routed=lead.routed_at is not None,
        organisation_recently_routed=recently_routed is not None,
    ):
        return False
    if not settings.lead_routing_enabled:
        return False
    org = await session.get(Org, lead.org_id) if lead.org_id else None
    signals = decode_signals(lead)
    errors: list[str] = []
    try:
        recipient_name = org.name if org else user.display_name if user else "a user"
        await asyncio.to_thread(
            send_email,
            settings,
            settings.lead_recipient_email,
            f"A useful moment to help {recipient_name}",
            context_card(lead, user, org, signals),
        )
    except (OSError, RuntimeError) as exc:
        errors.append(f"email: {exc}")
    if settings.lead_webhook_url and settings.lead_webhook_secret:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await post_webhook(
                    client,
                    settings.lead_webhook_url,
                    settings.lead_webhook_secret,
                    webhook_body(lead, user, org, signals),
                )
        except RuntimeError as exc:
            errors.append(str(exc))
    lead.route_attempts += 1
    lead.route_error = "; ".join(errors) or None
    if errors:
        return False
    lead.routed_at = datetime.now(UTC)
    lead.status = "routed"
    await session.flush()
    return True
