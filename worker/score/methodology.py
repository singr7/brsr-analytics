from __future__ import annotations

from pathlib import Path
from typing import Any

from worker.score.metrics import ROOT, load_scoring


def generate_methodology(config: dict[str, Any] | None = None) -> str:
    settings = config or load_scoring()
    substance = settings["substance"]
    completeness = settings["completeness"]
    assurance = settings["assurance_readiness"]
    return f"""# Substance and readiness score methodology

> Auto-generated from `scoring.yaml`; edit the configuration, not this file.

Method version: **{settings["method_version"]}**

## Completeness

Completeness is weighted field coverage on the QA-pinned disclosure set. BRSR Core fields
carry weight **{completeness["core_weight"]}** and remaining Essential fields carry weight
**{completeness["essential_weight"]}**. Components retain both present and possible counts.

## Substance versus boilerplate

The index combines quantified targets ({float(substance["quantified_target_weight"]):.0%}),
dated commitments ({float(substance["dated_commitment_weight"]):.0%}), named methodologies
({float(substance["named_methodology_weight"]):.0%}), and corpus originality
({float(substance["corpus_originality_weight"]):.0%}). Near-verbatim
{substance["phrase_words"]}-word phrases appearing in at least
{substance["boilerplate_company_threshold"]} companies are treated as boilerplate. The
shared-phrase table is regenerated from the pinned corpus on every rebuild.

## Assurance readiness

Assurance status contributes {float(assurance["assurance_status_weight"]):.0%}, BRSR Core
coverage contributes {float(assurance["core_coverage_weight"]):.0%}, and complete source
lineage contributes {float(assurance["lineage_quality_weight"]):.0%}.

## Cohorts and reproducibility

Sector percentiles are suppressed below **{settings["minimum_sector_size"]}** companies.
Every score stores its method version, component values, configuration hash, and a pinned
field-version anchor. `make rebuild-metrics` is a deterministic full rebuild.
"""


def write_methodology(path: Path | None = None) -> Path:
    target = path or ROOT / "docs" / "methodology" / "substance_index.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(generate_methodology(), encoding="utf-8")
    return target


def main() -> None:
    print(write_methodology())


if __name__ == "__main__":
    main()
