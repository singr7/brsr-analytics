from __future__ import annotations

import html
import io
import zipfile
from typing import Any

import fitz  # type: ignore[import-untyped]

from api.app.db.taxonomy import load_studio_schema
from worker.studio.engine import Finding, progress

SUBMISSION_NOTE = (
    "Submission-preparation note: these files support filing preparation only. The company and its "
    "advisors must review, approve and submit through the applicable exchange portal. "
    "BRSR Lens does "
    "not submit filings and does not assume the reporting entity's statutory liability."
)


def _lines(
    answers: dict[str, str], title: str, status: str, trail: list[dict[str, Any]]
) -> list[str]:
    schema = load_studio_schema()
    catalog = {field["field_key"]: field for field in schema["fields"]}
    lines = [
        title,
        "DRAFT — prepared with BRSR Lens" if status != "final" else "FINAL",
        SUBMISSION_NOTE,
    ]
    current = ""
    for key, value in sorted(
        answers.items(), key=lambda item: (catalog.get(item[0], {}).get("principle", ""), item[0])
    ):
        field = catalog.get(key)
        if not field:
            continue
        if field["principle"] != current:
            current = str(field["principle"])
            lines.append(f"Section {current}")
        lines.append(f"{field['label']}: {value}{' ' + field['unit'] if field.get('unit') else ''}")
    lines.append("Change-log and authorship trail")
    lines.extend(
        f"{item.get('field_key')}: {item.get('author')} · {item.get('review_status')}"
        for item in trail
    )
    return lines


def render_pdf(
    answers: dict[str, str], *, title: str, status: str, trail: list[dict[str, Any]]
) -> bytes:
    document = fitz.open()
    page = document.new_page()
    y = 56.0
    for index, line in enumerate(_lines(answers, title, status, trail)):
        if y > 790:
            page = document.new_page()
            y = 50
        size = 18 if index == 0 else 10
        page.insert_textbox(fitz.Rect(48, y, 548, y + 32), line, fontsize=size)
        y += 30 if index == 0 else 18
    return bytes(document.tobytes())


def render_docx(
    answers: dict[str, str], *, title: str, status: str, trail: list[dict[str, Any]]
) -> bytes:
    paragraphs = "".join(
        f"<w:p><w:r><w:t>{html.escape(line)}</w:t></w:r></w:p>"
        for line in _lines(answers, title, status, trail)
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{paragraphs}<w:sectPr/></w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
        'relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.'
        'openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    relationships = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
        '2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", relationships)
        archive.writestr("word/document.xml", document_xml)
    return output.getvalue()


def gap_report_data(
    answers: dict[str, str], findings: list[Finding], answer_meta: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    state = progress(answers, answer_meta)
    evidenced = sum(bool(meta.get("evidence_doc_id")) for meta in answer_meta.values())
    score = max(
        0, round((state["core_pct"] * 0.6) + (min(100, evidenced * 2) * 0.4) - len(findings) * 2)
    )
    priorities = [item.as_dict() for item in findings[:12]]
    agenda = [item["message"] for item in priorities[:5]] or [
        "Complete evidence review and final sign-off"
    ]
    return {
        "score": score,
        "core_coverage_pct": state["core_pct"],
        "evidence_answer_count": evidenced,
        "priorities": priorities,
        "bioedge_page": {
            "title": "How Panacea Bioedge can help",
            "label": "Advisory services — optional",
            "agenda": agenda,
        },
        "submission_note": SUBMISSION_NOTE,
    }


def render_gap_pdf(data: dict[str, Any]) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((48, 64), "Assurance-readiness gap report", fontsize=20)
    page.insert_text((48, 96), f"Readiness score: {data['score']}/100", fontsize=14)
    page.insert_text((48, 122), f"BRSR Core coverage: {data['core_coverage_pct']}%", fontsize=11)
    y = 160
    for item in data["priorities"]:
        page.insert_textbox(
            fitz.Rect(48, y, 540, y + 40), f"• {item['message']} — {item['fix_hint']}", fontsize=9
        )
        y += 36
    page = document.new_page()
    bioedge = data["bioedge_page"]
    page.insert_text((48, 64), str(bioedge["title"]), fontsize=20)
    page.insert_text((48, 90), str(bioedge["label"]), fontsize=10)
    y = 128
    for agenda in bioedge["agenda"]:
        page.insert_textbox(fitz.Rect(48, y, 540, y + 45), f"• {agenda}", fontsize=11)
        y += 40
    page.insert_textbox(fitz.Rect(48, 700, 540, 780), str(data["submission_note"]), fontsize=8)
    return bytes(document.tobytes())
