from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import yaml

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

