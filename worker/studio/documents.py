from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import fitz  # type: ignore[import-untyped]

ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}
DOC_KINDS = {
    "policy": ("policy", "code of conduct", "governance"),
    "hr_report": ("employee", "worker", "headcount", "training", "safety"),
    "energy_utility": ("electricity", "energy", "utility", "kwh", "gigajoule"),
    "sustainability_report": ("sustainability", "esg", "environment"),
    "prior_brsr": ("business responsibility", "brsr"),
    "csr_report": ("csr", "corporate social responsibility"),
}


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    kind: str
    pages: list[dict[str, object]]

    @property
    def text(self) -> str:
        return "\n".join(str(page["text"]) for page in self.pages)


def _office_text(content: bytes, suffix: str) -> str:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = (
            ["word/document.xml"]
            if suffix == ".docx"
            else sorted(name for name in archive.namelist() if name.startswith("xl/worksheets/"))
        )
        parts: list[str] = []
        for name in names:
            if name not in archive.namelist():
                continue
            root = ElementTree.fromstring(archive.read(name))
            parts.extend(node.text or "" for node in root.iter() if node.text)
        return " ".join(parts)


def classify_document(text: str) -> str:
    lowered = text.lower()
    scores = {
        kind: sum(lowered.count(token) for token in tokens) for kind, tokens in DOC_KINDS.items()
    }
    best = max(scores, key=lambda item: scores[item])
    return best if scores[best] else "other"


def parse_document(
    filename: str, content_type: str, content: bytes, max_bytes: int
) -> ParsedDocument:
    suffix = Path(filename).suffix.lower()
    if content_type not in ALLOWED_TYPES or ALLOWED_TYPES[content_type] != suffix:
        raise ValueError("Only matching PDF, DOCX and XLSX documents are accepted")
    if len(content) > max_bytes:
        raise ValueError(f"Document exceeds the {max_bytes} byte size cap")
    if suffix == ".pdf":
        document = fitz.open(stream=content, filetype="pdf")
        pages = [
            {"page": index + 1, "text": page.get_text()} for index, page in enumerate(document)
        ]
    else:
        pages = [{"page": 1, "text": _office_text(content, suffix)}]
    parsed = ParsedDocument(
        kind=classify_document(" ".join(str(p["text"]) for p in pages)), pages=pages
    )
    if not parsed.text.strip():
        raise ValueError("No readable text was found in the document")
    return parsed


def tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2}


def retrieve(
    query: str,
    documents: list[dict[str, Any]],
    *,
    studio_org_id: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    query_tokens = tokenize(query)
    candidates: list[tuple[float, dict[str, Any]]] = []
    for document in documents:
        if str(document["studio_org_id"]) != studio_org_id:
            continue
        for page in document.get("pages", []):
            text = str(page["text"])
            page_tokens = tokenize(text)
            score = len(query_tokens & page_tokens) / max(1, len(query_tokens | page_tokens))
            if score:
                candidates.append(
                    (
                        score,
                        {
                            "doc_id": str(document["id"]),
                            "page": int(page["page"]),
                            "text": text,
                            "score": score,
                        },
                    )
                )
    return [item for _, item in sorted(candidates, key=lambda row: row[0], reverse=True)[:limit]]
