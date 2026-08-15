import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from api.app.core.config import get_settings
from api.app.db.session import create_engine, create_session_factory
from api.app.models import User
from api.app.services.engagement import enforce_event_retention, send_weekly_digest
from api.app.services.leads import route_lead, score_user_lead
from worker.celery_app import celery_app


async def _score_and_route() -> int:
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    routed = 0
    async with factory() as session:
        users = (await session.scalars(select(User))).all()
        for user in users:
            lead = await score_user_lead(session, user)
            if lead and await route_lead(session, settings, lead):
                routed += 1
        await session.commit()
    await engine.dispose()
    return routed


@celery_app.task(name="worker.engagement.score_leads")  # type: ignore[untyped-decorator]
def score_leads_task() -> int:
    return asyncio.run(_score_and_route())


async def _weekly_digest() -> int:
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    async with factory() as session:
        count = await send_weekly_digest(session, settings)
    await engine.dispose()
    return count


@celery_app.task(name="worker.engagement.weekly_digest")  # type: ignore[untyped-decorator]
def weekly_digest_task() -> int:
    return asyncio.run(_weekly_digest())


async def _retention() -> int:
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    async with factory() as session:
        result = await enforce_event_retention(session, settings.analytics_retention_months)
        await session.commit()
    await engine.dispose()
    deleted = result["deleted"]
    if not isinstance(deleted, int):
        raise TypeError("retention result deleted count must be an integer")
    return deleted


@celery_app.task(name="worker.engagement.retain_events")  # type: ignore[untyped-decorator]
def retention_task() -> int:
    return asyncio.run(_retention())


def schedule_anchor() -> str:
    """Stable import-time probe for the offline task-registration test."""
    return datetime.now(UTC).date().isoformat()
