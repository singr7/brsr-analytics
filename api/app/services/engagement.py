from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.config import Settings
from api.app.models import Event, EventDailyAggregate, Lead
from api.app.services.auth import send_email
from api.app.services.leads import POSITIVE_OUTCOMES
from worker.parse.embeddings import hash_embedding

THEME_SEEDS = {
    "Assurance & Core": "assurance brsr core deadline audit readiness",
    "Climate & energy": "climate emissions energy renewable scope carbon intensity",
    "Water & waste": "water waste circularity recycling discharge",
    "Workforce & rights": "employee workforce diversity safety human rights grievance",
    "Peer benchmarking": "compare peer sector benchmark leader ranking",
}
FEATURE_LABELS = {
    "viewed_company": "Company deep-dives",
    "viewed_gap_panel": "Gap panels",
    "nlq_asked": "Ask the corpus",
    "export_generated": "Board exports",
    "studio_document_uploaded": "Studio evidence intake",
    "studio_answer_saved": "Studio questionnaire",
    "studio_gap_report": "Studio gap reports",
    "studio_export_created": "Studio exports",
    "deepdive_requested": "Expert deep-dives",
}


@dataclass(frozen=True, slots=True)
class AnalyticsEvent:
    name: str
    occurred_at: datetime
    user_id: str | None
    anon_id: str | None
    properties: dict[str, object]

    @property
    def identity(self) -> str:
        return self.user_id or self.anon_id or "unknown"


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def nlq_theme(question: str) -> str:
    vector = hash_embedding(question, dimensions=256)
    scores = {
        label: _dot(vector, hash_embedding(seed, dimensions=256))
        for label, seed in THEME_SEEDS.items()
    }
    label, score = max(scores.items(), key=lambda item: item[1])
    return label if score > 0 else "Other disclosure questions"


def funnel(
    events: Iterable[AnalyticsEvent], steps: list[tuple[str, frozenset[str]]]
) -> list[dict[str, object]]:
    ordered = sorted(events, key=lambda item: item.occurred_at)
    reached: dict[str, set[str]] = defaultdict(set)
    stage_by_identity: dict[str, int] = defaultdict(int)
    for event in ordered:
        stage = stage_by_identity[event.identity]
        if stage >= len(steps):
            continue
        _, names = steps[stage]
        if event.name in names:
            reached[steps[stage][0]].add(event.identity)
            stage_by_identity[event.identity] += 1
    output: list[dict[str, object]] = []
    previous: int | None = None
    for label, _ in steps:
        count = len(reached[label])
        conversion = None if previous is None else round(count / previous, 4) if previous else 0.0
        output.append(
            {"name": label, "users": count, "conversion_from_previous": conversion}
        )
        previous = count
    return output


def analytics_snapshot(
    events: list[AnalyticsEvent], now: datetime | None = None
) -> dict[str, object]:
    current = now or datetime.now(UTC)
    usage = Counter(FEATURE_LABELS[event.name] for event in events if event.name in FEATURE_LABELS)
    themes = Counter(
        nlq_theme(str(event.properties.get("question", "")))
        for event in events
        if event.name == "nlq_asked" and event.properties.get("question")
    )
    sectors = Counter(
        str(event.properties["sector"])
        for event in events
        if event.properties.get("sector")
    )
    return {
        "generated_at": current,
        "range_start": min((event.occurred_at for event in events), default=current),
        "visit_to_pro": funnel(
            events,
            [
                ("Visit", frozenset({"page_viewed"})),
                ("Signup", frozenset({"signup_completed"})),
                ("Pro", frozenset({"plan_changed_to_pro"})),
            ],
        ),
        "studio_to_export": funnel(
            events,
            [
                ("Studio start", frozenset({"studio_answer_saved", "studio_document_uploaded"})),
                ("Gap report", frozenset({"studio_gap_report"})),
                ("Export", frozenset({"studio_export_created"})),
            ],
        ),
        "feature_usage": [
            {"name": name, "count": count} for name, count in usage.most_common()
        ],
        "nlq_themes": [
            {"name": name, "count": count} for name, count in themes.most_common()
        ],
        "sector_interest": [
            {"name": name, "count": count} for name, count in sectors.most_common()
        ],
    }


async def load_analytics(
    session: AsyncSession, days: int = 30, now: datetime | None = None
) -> dict[str, object]:
    current = now or datetime.now(UTC)
    rows = (
        await session.scalars(
            select(Event).where(Event.ts >= current - timedelta(days=days)).order_by(Event.ts)
        )
    ).all()
    return analytics_snapshot(
        [
            AnalyticsEvent(
                row.name,
                row.ts,
                str(row.user_id) if row.user_id else None,
                str(row.anon_id) if row.anon_id else None,
                row.props_json,
            )
            for row in rows
        ],
        current,
    )


def digest_text(snapshot: dict[str, object]) -> str:
    usage = cast(list[dict[str, object]], snapshot["feature_usage"])
    themes = cast(list[dict[str, object]], snapshot["nlq_themes"])
    top_features = "\n".join(f"- {item['name']}: {item['count']}" for item in usage[:5])
    top_themes = "\n".join(f"- {item['name']}: {item['count']}" for item in themes[:5])
    return (
        "Here is the weekly BRSR Lens engagement digest.\n\n"
        f"Most-used workflows:\n{top_features or '- No recorded use'}\n\n"
        f"Questions the market asked:\n{top_themes or '- No NLQ questions recorded'}\n\n"
        "Use these patterns to improve the product and editorial programme; "
        "never to single out users."
    )


async def send_weekly_digest(session: AsyncSession, settings: Settings) -> int:
    snapshot = await load_analytics(session, days=7)
    recipients = [
        item.strip()
        for item in settings.analytics_digest_recipients.split(",")
        if item.strip()
    ]
    for recipient in recipients:
        await asyncio.to_thread(
            send_email,
            settings,
            recipient,
            "BRSR Lens · weekly engagement digest",
            digest_text(snapshot),
        )
    return len(recipients)


async def enforce_event_retention(
    session: AsyncSession, retention_months: int, now: datetime | None = None
) -> dict[str, object]:
    current = now or datetime.now(UTC)
    cutoff_date = (current - timedelta(days=retention_months * 31)).date()
    event_day = func.date(Event.ts)
    rows = (
        await session.execute(
            select(event_day, Event.name, func.count())
            .where(Event.ts < datetime.combine(cutoff_date, datetime.min.time(), tzinfo=UTC))
            .group_by(event_day, Event.name)
        )
    ).all()
    for day, name, count in rows:
        aggregate = await session.scalar(
            select(EventDailyAggregate).where(
                EventDailyAggregate.day == day,
                EventDailyAggregate.name == name,
                EventDailyAggregate.dimension == "all",
                EventDailyAggregate.dimension_value == "all",
            )
        )
        if aggregate is None:
            session.add(
                EventDailyAggregate(
                    day=day,
                    name=name,
                    dimension="all",
                    dimension_value="all",
                    event_count=int(count),
                )
            )
        else:
            aggregate.event_count = int(count)
    result = await session.execute(
        delete(Event).where(
            Event.ts < datetime.combine(cutoff_date, datetime.min.time(), tzinfo=UTC)
        )
    )
    return {
        "cutoff": cutoff_date,
        "aggregated": len(rows),
        "deleted": int(result.rowcount),  # type: ignore[attr-defined]
    }


async def lead_quality(session: AsyncSession) -> list[dict[str, object]]:
    leads = (await session.scalars(select(Lead).where(Lead.outcome.is_not(None)))).all()
    totals: Counter[str] = Counter()
    positives: Counter[str] = Counter()
    for lead in leads:
        timeline = lead.signals_json.get("timeline", [])
        keys = {
            str(item["key"])
            for item in timeline
            if isinstance(item, dict) and item.get("key")
        } if isinstance(timeline, list) else set()
        for key in keys:
            totals[key] += 1
            if lead.outcome in POSITIVE_OUTCOMES:
                positives[key] += 1
    return [
        {
            "signal": key,
            "leads": total,
            "positive_outcomes": positives[key],
            "conversion_rate": round(positives[key] / total, 4),
        }
        for key, total in totals.most_common()
    ]
