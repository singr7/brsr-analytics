from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

SECTION_ANCHORS = {
    "a": ("section a", "general disclosures"),
    "b": ("section b", "management and process disclosures"),
    "p1": ("principle 1", "integrity"),
    "p2": ("principle 2", "sustainable and safe goods"),
    "p3": ("principle 3", "employee well-being"),
    "p4": ("principle 4", "stakeholder"),
    "p5": ("principle 5", "human rights"),
    "p6": ("principle 6", "environment"),
    "p7": ("principle 7", "public policy"),
    "p8": ("principle 8", "inclusive growth"),
    "p9": ("principle 9", "consumer value"),
}


@dataclass(frozen=True, slots=True)
class TableRegion:
    x0: float
    y0: float
    x1: float
    y1: float
    rows: int
    columns: int


@dataclass(slots=True)
class ParsedPage:
    page_no: int
    text: str
    image_png: bytes
    section_key: str | None
    locator_confidence: float
    table_regions: list[TableRegion] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SectionLocation:
    start_page: int
    end_page: int
    confidence: float
    ambiguous: bool
    page_sections: dict[int, str]


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _anchor_score(text: str, anchors: tuple[str, ...]) -> float:
    normal = _normalise(text)
    score = 0.0
    for anchor in anchors:
        if anchor in normal:
            score = max(score, 1.0)
        else:
            for line in normal.split("."):
                score = max(score, SequenceMatcher(None, anchor, line[: len(anchor) + 20]).ratio())
    return score


def locate_brsr_sections(page_texts: list[str]) -> SectionLocation:
    if not page_texts:
        return SectionLocation(0, 0, 0.0, True, {})
    candidates: list[tuple[float, int]] = []
    for index, text in enumerate(page_texts, start=1):
        normal = _normalise(text)
        title = 1.0 if "business responsibility and sustainability report" in normal else 0.0
        section_a = _anchor_score(text, SECTION_ANCHORS["a"])
        principle = max(
            _anchor_score(text, value)
            for key, value in SECTION_ANCHORS.items()
            if key.startswith("p")
        )
        score = min(1.0, title * 0.55 + section_a * 0.60 + principle * 0.10)
        if section_a >= 0.72 or title:
            candidates.append((score, index))
    if not candidates:
        return SectionLocation(1, len(page_texts), 0.0, True, {})
    candidates.sort(reverse=True)
    confidence, start = candidates[0]
    ambiguous = len(candidates) > 1 and candidates[1][0] >= confidence - 0.08

    page_sections: dict[int, str] = {}
    active: str | None = None
    section_hits = 0
    for page_no in range(start, len(page_texts) + 1):
        scored = [
            (_anchor_score(page_texts[page_no - 1], anchors), key)
            for key, anchors in SECTION_ANCHORS.items()
        ]
        best_score, best_key = max(scored)
        if best_score >= 0.72:
            active = best_key
            section_hits += 1
        if active:
            page_sections[page_no] = active
    coverage = min(1.0, section_hits / 5)
    final_confidence = round(confidence * 0.7 + coverage * 0.3, 4)
    return SectionLocation(start, len(page_texts), final_confidence, ambiguous, page_sections)


def detect_table_regions(
    words: list[tuple[float, float, float, float, str, Any]],
) -> list[TableRegion]:
    """Flag dense aligned word boxes without claiming semantic table recovery."""
    if len(words) < 8:
        return []
    rows: dict[int, list[tuple[float, float, float, float, str, Any]]] = {}
    for word in words:
        rows.setdefault(round(word[1] / 5), []).append(word)
    aligned = [row for row in rows.values() if len(row) >= 3]
    if len(aligned) < 2:
        return []
    column_buckets = {round(word[0] / 12) for row in aligned for word in row}
    if len(column_buckets) < 3:
        return []
    flat = [word for row in aligned for word in row]
    return [
        TableRegion(
            min(word[0] for word in flat),
            min(word[1] for word in flat),
            max(word[2] for word in flat),
            max(word[3] for word in flat),
            len(aligned),
            len(column_buckets),
        )
    ]


def parse_pdf(content: bytes) -> tuple[list[ParsedPage], SectionLocation]:
    try:
        import fitz  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover - dependency failure is operational
        raise RuntimeError("PyMuPDF is required to parse PDF filings") from exc
    document = fitz.open(stream=content, filetype="pdf")
    texts = [page.get_text("text") for page in document]
    location = locate_brsr_sections(texts)
    pages: list[ParsedPage] = []
    scale = 150 / 72
    for page_no in range(location.start_page, location.end_page + 1):
        page = document[page_no - 1]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        pages.append(
            ParsedPage(
                page_no=page_no,
                text=texts[page_no - 1],
                image_png=pixmap.tobytes("png"),
                section_key=location.page_sections.get(page_no),
                locator_confidence=location.confidence,
                table_regions=detect_table_regions(page.get_text("words")),
            )
        )
    document.close()
    return pages, location
