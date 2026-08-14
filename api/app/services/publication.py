from dataclasses import dataclass

QA_PASSED = frozenset({"sampled_ok", "corrected"})


@dataclass(frozen=True, slots=True)
class ExtractionVersion:
    version: int
    qa_status: str


def latest_publishable(versions: list[ExtractionVersion]) -> ExtractionVersion | None:
    """Return the newest QA-passed version; unreviewed versions never affect publication."""
    candidates = (item for item in versions if item.qa_status in QA_PASSED)
    return max(candidates, key=lambda item: item.version, default=None)
