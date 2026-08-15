import json
import zipfile
from io import BytesIO
from xml.etree import ElementTree as ET

from api.app.db.taxonomy import load_studio_schema
from worker.exportgen.documents import gap_report_data, render_docx, render_gap_pdf, render_pdf
from worker.exportgen.xbrl import export_gate, generate_instance, validate_instance
from worker.studio.documents import parse_document, retrieve
from worker.studio.engine import (
    Finding,
    prior_prefill_candidates,
    progress,
    validate_filing,
    validate_value,
)
from worker.studio.mapper import (
    Proposal,
    document_gap_report,
    quote_is_verbatim,
    within_token_quota,
)
from worker.studio.schema import lint_schema, schema_stats


def _complete_answers() -> dict[str, str]:
    answers = {}
    for field in load_studio_schema()["fields"]:
        if field.get("repeating_group"):
            value = "[]"
        elif field["dtype"] in {"number", "integer"}:
            value = "0"
        elif field["dtype"] == "boolean":
            value = "true"
        elif field["dtype"] == "date":
            value = "2025-03-31"
        else:
            value = "Disclosed"
        answers[field["field_key"]] = value
    return answers


def test_full_schema_lints_and_covers_all_sections() -> None:
    assert lint_schema() == []
    stats = schema_stats()
    assert stats["schema_version"] == "1.0.0"
    assert stats["sections"] == 12
    assert stats["fields"] >= 250
    assert stats["core_fields"] >= 9


def test_validation_golden_has_exactly_fifteen_seeded_errors() -> None:
    answers = _complete_answers()
    required = [
        field["field_key"]
        for field in load_studio_schema()["fields"]
        if field.get("required", True)
        and not field.get("leadership")
        and not field.get("condition")
    ][:15]
    for key in required:
        answers.pop(key)
    findings = validate_filing(answers)
    assert len(findings) == 15
    assert {item.field_key for item in findings} == set(required)


def test_value_grid_progress_and_prior_prefill_contracts() -> None:
    schema = load_studio_schema()
    percentage = next(field for field in schema["fields"] if field.get("unit") == "percent")
    assert validate_value(percentage, "72.5", "percent") == "72.5"
    group = next(field for field in schema["fields"] if field.get("repeating_group"))
    assert validate_value(group, json.dumps([{"description": "Product"}]))
    complete = _complete_answers()
    assert progress(complete)["complete"] is True
    candidates = prior_prefill_candidates({}, {"a.basics.company_name": "Prior Ltd"})
    assert candidates == [
        {
            "field_key": "a.basics.company_name",
            "value": "Prior Ltd",
            "status": "candidate",
            "author_after_accept": "user",
        }
    ]


def test_org_isolation_applies_to_document_retrieval() -> None:
    docs = [
        {
            "id": "a",
            "studio_org_id": "org-a",
            "pages": [{"page": 1, "text": "Energy consumed was 100 GJ"}],
        },
        {
            "id": "b",
            "studio_org_id": "org-b",
            "pages": [{"page": 1, "text": "Energy consumed was 999 GJ"}],
        },
    ]
    results = retrieve("energy consumed", docs, studio_org_id="org-b")
    assert {item["doc_id"] for item in results} == {"b"}
    assert "100" not in " ".join(str(item["text"]) for item in results)


def test_document_intake_quote_tripwire_gap_and_quota() -> None:
    docx = render_docx(
        {"a.basics.company_name": "Acme"},
        title="Human resources report",
        status="draft",
        trail=[],
    )
    parsed = parse_document(
        "hr.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        docx,
        1_000_000,
    )
    assert parsed.pages
    assert quote_is_verbatim("Human resources report", parsed.text)
    assert not quote_is_verbatim("fabricated supporting evidence", parsed.text)
    proposal = Proposal("p3.essential.processes", "Process", None, "doc", 1, "Process", 0.9)
    report = document_gap_report([proposal], set())
    assert report["gaps"]
    assert within_token_quota(90, 10, 100)
    assert not within_token_quota(90, 11, 100)


def test_export_gate_blocks_unreviewed_ai_and_outputs_are_structural() -> None:
    answers = _complete_answers()
    key = "a.basics.company_name"
    gate = export_gate(answers, {key: {"author": "ai", "review_status": "unreviewed"}})
    assert not gate.allowed
    assert any(item.field_key == key for item in gate.findings)
    clean = export_gate(answers, {})
    assert clean.allowed
    instance = generate_instance(answers, entity_identifier="L12345MH2020PLC123456", fy=2025)
    assert validate_instance(instance) == []
    assert ET.fromstring(instance).tag.endswith("xbrl")
    trail = [{"field_key": key, "author": "user", "review_status": "accepted"}]
    pdf = render_pdf(answers, title="Fixture BRSR", status="draft", trail=trail)
    docx = render_docx(answers, title="Fixture BRSR", status="draft", trail=trail)
    assert pdf.startswith(b"%PDF")
    with zipfile.ZipFile(BytesIO(docx)) as archive:
        xml = archive.read("word/document.xml")
    assert b"DRAFT" in xml and b"Submission-preparation note" in xml


def test_gap_report_contains_contextual_bioedge_page() -> None:
    data = gap_report_data(
        {},
        [
            Finding(
                "error",
                "p6.e1.energy_total_gj",
                "Energy evidence missing",
                "Upload utility bills",
                "L3",
            )
        ],
        {},
    )
    assert data["bioedge_page"]["title"] == "How Panacea Bioedge can help"
    assert "Energy evidence missing" in data["bioedge_page"]["agenda"]
    assert render_gap_pdf(data).startswith(b"%PDF")
