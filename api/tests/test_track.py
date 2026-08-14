import pytest

from api.app.services.track import InMemoryEventSink, Tracker


def test_registered_event_is_captured() -> None:
    sink = InMemoryEventSink()
    tracker = Tracker(sink)
    tracker.track("demo_chart_viewed", {"chart": "readiness"})
    assert sink.events[0].properties == {"chart": "readiness"}


def test_unregistered_event_fails() -> None:
    tracker = Tracker(InMemoryEventSink())
    with pytest.raises(ValueError, match="Unregistered event"):
        tracker.track("typo_event")

