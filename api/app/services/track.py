from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID, uuid4

import yaml
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.models import Event as EventRow
from api.app.models import User

REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True, slots=True)
class Event:
    name: str
    properties: dict[str, Any]
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class EventSink(Protocol):
    def emit(self, event: Event) -> None: ...


class InMemoryEventSink:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def emit(self, event: Event) -> None:
        self.events.append(event)


class Tracker:
    def __init__(self, sink: EventSink, registry_path: Path | None = None) -> None:
        path = registry_path or REPO_ROOT / "events.yaml"
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        self.registered = frozenset(document.get("events", {}).keys())
        self.sink = sink

    def track(self, name: str, properties: dict[str, Any] | None = None) -> None:
        if name not in self.registered:
            raise ValueError(f"Unregistered event: {name}")
        self.sink.emit(Event(name=name, properties=properties or {}))


def event_registry(registry_path: Path | None = None) -> frozenset[str]:
    path = registry_path or REPO_ROOT / "events.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    return frozenset(document.get("events", {}).keys())


async def persist_events(
    session: AsyncSession,
    events: list[dict[str, Any]],
    anon_id: UUID | None,
    user_id: UUID | None,
) -> int:
    if user_id is not None and await session.scalar(
        select(User.analytics_opt_out).where(User.id == user_id)
    ):
        return 0
    registered = event_registry()
    unknown = {str(item["name"]) for item in events} - registered
    if unknown:
        raise ValueError(f"Unregistered event: {sorted(unknown)[0]}")
    now = datetime.now(UTC)
    rows = [
        {
            "id": uuid4(),
            "anon_id": anon_id,
            "user_id": user_id,
            "session_id": item["session_id"],
            "name": item["name"],
            "props_json": item.get("properties", {}),
            "ts": item.get("occurred_at") or now,
        }
        for item in events
    ]
    await session.execute(insert(EventRow), rows)
    return len(rows)


async def merge_anonymous_history(
    session: AsyncSession, anon_id: UUID | None, user_id: UUID
) -> int:
    if anon_id is None:
        return 0
    result = await session.execute(
        update(EventRow)
        .where(EventRow.anon_id == anon_id, EventRow.user_id.is_(None))
        .values(user_id=user_id)
    )
    return int(result.rowcount)  # type: ignore[attr-defined]
