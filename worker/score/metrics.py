from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class MetricCandidate:
    company_id: str
    fy: int
    sector: str
    metric_key: str
    value: Decimal
    pin_id: str
    contributing_pin_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MaterializedMetric:
    candidate: MetricCandidate
    percentile_sector: Decimal | None
    percentile_all: Decimal
    yoy_delta: Decimal | None


def load_scoring(path: Path | None = None) -> dict[str, Any]:
    document = yaml.safe_load((path or ROOT / "scoring.yaml").read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not document.get("method_version"):
        raise ValueError("scoring.yaml requires method_version")
    return document


@dataclass(frozen=True, slots=True)
class ScreenFailure:
    company_id: str
    fy: int
    screen: str
    metric_key: str
    detail: str


def _dependents(config: dict[str, Any]) -> dict[str, set[str]]:
    """Map each source metric key to the metric keys computed from it."""
    dependents: dict[str, set[str]] = defaultdict(set)
    for additive in config.get("additive_metrics", []):
        for key in additive["addends"]:
            dependents[str(key)].add(str(additive["metric_key"]))
    for derived in config.get("derived_metrics", []):
        sources = (
            [str(derived["numerator"])]
            if "numerator" in derived
            else [str(key) for key in derived["numerators"]]
        )
        sources.append(str(derived["denominator"]))
        for key in sources:
            dependents[key].add(str(derived["metric_key"]))
    return dependents


def _closure(keys: set[str], dependents: dict[str, set[str]]) -> set[str]:
    """Expand a set of withheld keys to everything computed from them."""
    resolved = set(keys)
    pending = list(keys)
    while pending:
        for dependent in dependents.get(pending.pop(), set()):
            if dependent not in resolved:
                resolved.add(dependent)
                pending.append(dependent)
    return resolved


def screen_implausible(
    candidates: list[MetricCandidate], config: dict[str, Any]
) -> tuple[list[MetricCandidate], list[ScreenFailure]]:
    """Withhold metrics that break an arithmetic identity asserted by the disclosure itself.

    A component reported at a different scale from its total is the failure mode that unit
    and scale mistakes actually produce, and it breaks these identities. Deliberately no
    physical-ratio bands: Scope 1 legitimately includes non-energy fugitive and process
    emissions, so an emissions-per-energy band would encode a rule that is not true.
    """
    screens = config.get("plausibility_screens") or {}
    identities = screens.get("identities") or []
    non_negative = {str(key) for key in screens.get("non_negative") or []}
    if not identities and not non_negative:
        return candidates, []
    tolerance = Decimal(str(screens.get("tolerance", "0.01")))
    dependents = _dependents(config)

    by_filing: dict[tuple[str, int], dict[str, Decimal]] = defaultdict(dict)
    for candidate in candidates:
        by_filing[(candidate.company_id, candidate.fy)][candidate.metric_key] = candidate.value

    failures: list[ScreenFailure] = []
    withheld: dict[tuple[str, int], set[str]] = defaultdict(set)
    for (company_id, fy), values in by_filing.items():
        for identity in identities:
            total_key = str(identity["total"])
            part_keys = [str(key) for key in identity["parts"]]
            if total_key not in values or any(key not in values for key in part_keys):
                continue
            total = values[total_key]
            parts_sum = sum((values[key] for key in part_keys), Decimal(0))
            if abs(total - parts_sum) > tolerance * max(abs(total), Decimal(1)):
                withheld[(company_id, fy)].add(total_key)
                failures.append(
                    ScreenFailure(
                        company_id=company_id,
                        fy=fy,
                        screen="identity",
                        metric_key=total_key,
                        detail=f"{total_key}={total} but components sum to {parts_sum}",
                    )
                )
        for key in non_negative & values.keys():
            if values[key] < 0:
                withheld[(company_id, fy)].add(key)
                failures.append(
                    ScreenFailure(
                        company_id=company_id,
                        fy=fy,
                        screen="non_negative",
                        metric_key=key,
                        detail=f"{key}={values[key]} is negative",
                    )
                )

    blocked = {
        filing_key: _closure(keys, dependents) for filing_key, keys in withheld.items()
    }
    kept = [
        candidate
        for candidate in candidates
        if candidate.metric_key
        not in blocked.get((candidate.company_id, candidate.fy), set())
    ]
    return kept, failures


def _percentile(value: Decimal, cohort: list[Decimal]) -> Decimal:
    if len(cohort) <= 1:
        return Decimal(100)
    below = sum(item < value for item in cohort)
    equal = sum(item == value for item in cohort)
    rank = Decimal(below) + (Decimal(equal - 1) / 2)
    return (rank / Decimal(len(cohort) - 1) * 100).quantize(Decimal("0.0001"))


def materialize_percentiles(
    candidates: list[MetricCandidate], *, minimum_sector_size: int = 5
) -> list[MaterializedMetric]:
    all_cohorts: dict[tuple[int, str], list[Decimal]] = defaultdict(list)
    sector_cohorts: dict[tuple[int, str, str], list[Decimal]] = defaultdict(list)
    history: dict[tuple[str, str], dict[int, Decimal]] = defaultdict(dict)
    for item in candidates:
        all_cohorts[(item.fy, item.metric_key)].append(item.value)
        sector_cohorts[(item.fy, item.metric_key, item.sector)].append(item.value)
        history[(item.company_id, item.metric_key)][item.fy] = item.value
    output: list[MaterializedMetric] = []
    for item in sorted(candidates, key=lambda row: (row.company_id, row.fy, row.metric_key)):
        sector = sector_cohorts[(item.fy, item.metric_key, item.sector)]
        previous = history[(item.company_id, item.metric_key)].get(item.fy - 1)
        output.append(
            MaterializedMetric(
                item,
                _percentile(item.value, sector) if len(sector) >= minimum_sector_size else None,
                _percentile(item.value, all_cohorts[(item.fy, item.metric_key)]),
                item.value - previous if previous is not None else None,
            )
        )
    return output


def completeness_score(
    present_fields: set[str], core_fields: set[str], all_fields: set[str], config: dict[str, Any]
) -> tuple[Decimal, dict[str, object]]:
    core_weight = Decimal(str(config["core_weight"]))
    essential_weight = Decimal(str(config["essential_weight"]))
    essential = all_fields - core_fields
    achieved = (
        Decimal(len(present_fields & core_fields)) * core_weight
        + Decimal(len(present_fields & essential)) * essential_weight
    )
    possible = Decimal(len(core_fields)) * core_weight + Decimal(len(essential)) * essential_weight
    value = Decimal(0) if not possible else (achieved / possible * 100).quantize(Decimal("0.0001"))
    return value, {
        "core_present": len(present_fields & core_fields),
        "core_total": len(core_fields),
        "essential_present": len(present_fields & essential),
        "essential_total": len(essential),
        "weighted_points": str(achieved),
        "weighted_possible": str(possible),
    }


def narrative_signals(text: str) -> dict[str, bool]:
    lower = text.lower()
    quantified = bool(
        re.search(r"\b\d+(?:\.\d+)?\s*(?:%|percent\b|mt\b|gj\b|kl\b|tco2e\b)", lower)
        and re.search(r"\b(?:target|commit|reduce|achieve)\w*\b", lower)
    )
    dated = bool(re.search(r"\b(?:by|before|until)\s+(?:fy\s*)?20\d{2}\b", lower))
    methodology = bool(
        re.search(
            r"\b(?:ghg protocol|iso\s*\d+|gri|sasb|science based targets|methodology)\b", lower
        )
    )
    return {"quantified_target": quantified, "dated_commitment": dated, "methodology": methodology}


def phrase_frequencies(
    documents: dict[str, list[str]], *, phrase_words: int = 8
) -> dict[str, tuple[str, int]]:
    companies_by_phrase: dict[str, set[str]] = defaultdict(set)
    phrase_text: dict[str, str] = {}
    for company, texts in documents.items():
        for text in texts:
            words = re.findall(r"[a-z0-9]+", text.lower())
            for index in range(max(0, len(words) - phrase_words + 1)):
                phrase = " ".join(words[index : index + phrase_words])
                digest = hashlib.sha256(phrase.encode()).hexdigest()
                companies_by_phrase[digest].add(company)
                phrase_text[digest] = phrase
    return {
        digest: (phrase_text[digest], len(companies))
        for digest, companies in companies_by_phrase.items()
    }


def substance_score(
    texts: list[str], boilerplate_hashes: set[str], config: dict[str, Any]
) -> tuple[Decimal, dict[str, object]]:
    signals = [narrative_signals(text) for text in texts]
    combined = {
        name: any(signal[name] for signal in signals)
        for name in ("quantified_target", "dated_commitment", "methodology")
    }
    phrase_words = int(config["phrase_words"])
    own_phrases = phrase_frequencies({"company": texts}, phrase_words=phrase_words)
    boilerplate = sum(digest in boilerplate_hashes for digest in own_phrases)
    originality = Decimal(1) - (Decimal(boilerplate) / Decimal(max(1, len(own_phrases))))
    value = (
        Decimal(combined["quantified_target"]) * Decimal(str(config["quantified_target_weight"]))
        + Decimal(combined["dated_commitment"]) * Decimal(str(config["dated_commitment_weight"]))
        + Decimal(combined["methodology"]) * Decimal(str(config["named_methodology_weight"]))
        + originality * Decimal(str(config["corpus_originality_weight"]))
    ) * 100
    return value.quantize(Decimal("0.0001")), {
        **combined,
        "originality": str(originality.quantize(Decimal("0.0001"))),
        "boilerplate_phrases": boilerplate,
        "phrase_count": len(own_phrases),
    }


def assurance_readiness_score(
    assurance_present: bool,
    core_coverage: Decimal,
    lineage_quality: Decimal,
    config: dict[str, Any],
) -> tuple[Decimal, dict[str, object]]:
    assurance = Decimal(int(assurance_present))
    value = (
        assurance * Decimal(str(config["assurance_status_weight"]))
        + core_coverage * Decimal(str(config["core_coverage_weight"]))
        + lineage_quality * Decimal(str(config["lineage_quality_weight"]))
    ) * 100
    return value.quantize(Decimal("0.0001")), {
        "assurance_status": str(assurance),
        "core_coverage": str(core_coverage),
        "lineage_quality": str(lineage_quality),
    }


def value_counts(values: list[str]) -> dict[str, int]:
    return dict(Counter(values))
