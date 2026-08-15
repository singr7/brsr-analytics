from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from api.app.services.llm import FakeLLM
from api.app.services.publication_policy import field_family
from worker.extract.run import extract_batch

ROOT = Path(__file__).resolve().parents[2]


async def benchmark(path: Path | None = None) -> dict[str, float]:
    golden_path = path or ROOT / "testdata" / "extraction" / "golden.json"
    case: dict[str, Any] = json.loads(golden_path.read_text(encoding="utf-8"))
    pages = {int(key): str(value) for key, value in case["pages"].items()}
    result = await extract_batch(FakeLLM(), str(case["section"]), list(case["field_defs"]), pages)
    expected = {str(key): str(value) for key, value in case["expected"].items()}
    family_totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    actual = {
        item.item.field_key: str(item.item.value)
        for item in result.fields
        if not item.flags and item.confidence > 0
    }
    for key, value in expected.items():
        totals = family_totals[field_family(key)]
        totals[1] += 1
        totals[0] += int(actual.get(key) == value)
    return {family: correct / total for family, (correct, total) in family_totals.items()}


def main() -> None:
    results = asyncio.run(benchmark())
    for family, accuracy in sorted(results.items()):
        print(f"{family}: {accuracy:.2%}")
    if not results or min(results.values()) < 0.98:
        raise SystemExit("Extraction benchmark is below the 98% publication target")


if __name__ == "__main__":
    main()
