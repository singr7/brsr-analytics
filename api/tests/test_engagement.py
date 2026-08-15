from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from api.app.models import Lead, Org, User
from api.app.services.engagement import AnalyticsEvent, analytics_snapshot, nlq_theme
from api.app.services.leads import (
    EventFact,
    context_card,
    decode_signals,
    post_webhook,
    routing_eligible,
    score_events,
    signals_document,
    webhook_signature,
)


def event(name: str, now: datetime, **properties: object) -> EventFact:
    return EventFact(name=name, occurred_at=now, properties=properties)


def test_scoring_golden_caps_repeats_and_recognises_intent() -> None:
    now = datetime(2026, 8, 15, tzinfo=UTC)
    events = [
        event("viewed_gap_panel", now - timedelta(days=i), company="Aster Steel")
        for i in range(5)
    ]
    events.extend(
        [
            event("nlq_asked", now, question="What is the BRSR Core assurance deadline?"),
            event("pricing_viewed", now),
            event("viewed_gap_panel", now - timedelta(days=31)),
        ]
    )
    result = score_events(events, now=now)
    assert result.score == 55
    assert [signal.key for signal in result.signals].count("viewed_gap_panel") == 3
    assert result.instant_route is False


def test_deepdive_is_an_instant_route_signal() -> None:
    now = datetime(2026, 8, 15, tzinfo=UTC)
    result = score_events([event("deepdive_requested", now)], now=now)
    assert result.score == 50
    assert result.instant_route is True


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, True),
        ({"opted_out": True}, False),
        ({"already_routed": True}, False),
        ({"organisation_recently_routed": True}, False),
        ({"score": 49}, False),
        ({"score": 0, "instant": True}, True),
    ],
)
def test_route_suppression_is_absolute(overrides: dict[str, object], expected: bool) -> None:
    values: dict[str, object] = {
        "score": 50,
        "threshold": 50,
        "instant": False,
        "opted_out": False,
        "already_routed": False,
        "organisation_recently_routed": False,
    }
    values.update(overrides)
    assert routing_eligible(**values) is expected  # type: ignore[arg-type]


class Poster:
    def __init__(self) -> None:
        self.calls = 0
        self.headers: dict[str, str] = {}

    async def post(self, url: str, *, content: bytes, headers: dict[str, str]) -> httpx.Response:
        self.calls += 1
        self.headers = headers
        return httpx.Response(503 if self.calls < 3 else 202)


async def test_webhook_signature_and_bounded_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("api.app.services.leads.asyncio.sleep", AsyncMock())
    poster = Poster()
    body = b'{"lead":"fixture"}'
    assert await post_webhook(poster, "https://crm.example/leads", "secret", body) == 202
    assert poster.calls == 3
    assert poster.headers["X-BRSRLens-Signature"] == webhook_signature("secret", body)


def test_context_card_reads_like_a_colleague_note() -> None:
    now = datetime(2026, 8, 15, tzinfo=UTC)
    score = score_events(
        [event("studio_gap_report", now, company="Aster Steel"), event("pricing_viewed", now)],
        now=now,
    )
    lead = Lead(id=uuid4(), score=Decimal(score.score), signals_json=signals_document(score))
    user = User(
        id=uuid4(),
        email="anita@example.com",
        display_name="Anita Rao",
        password_hash="unused",
        plan_tier="pro",
        is_admin=False,
        analytics_opt_out=False,
    )
    org = Org(id=uuid4(), name="Example Ltd", slug="example", plan_tier="pro")
    card = context_card(lead, user, org, decode_signals(lead))
    assert "may benefit from a timely, useful conversation" in card
    assert "Use this context to be relevant, not intrusive" in card
    assert "Do not mention tracking or the score" in card


def test_funnels_count_ordered_people_not_raw_events() -> None:
    now = datetime(2026, 8, 15, tzinfo=UTC)
    facts = [
        AnalyticsEvent("page_viewed", now, "u1", None, {}),
        AnalyticsEvent("page_viewed", now, "u1", None, {}),
        AnalyticsEvent("signup_completed", now + timedelta(minutes=1), "u1", None, {}),
        AnalyticsEvent("plan_changed_to_pro", now + timedelta(minutes=2), "u1", None, {}),
        AnalyticsEvent("signup_completed", now, "u2", None, {}),
    ]
    snapshot = analytics_snapshot(facts, now)
    assert [step["users"] for step in snapshot["visit_to_pro"]] == [1, 1, 1]  # type: ignore[index]


def test_nlq_embedding_theme_is_deterministic() -> None:
    assert nlq_theme("Compare assurance readiness and BRSR Core deadlines") == "Assurance & Core"
