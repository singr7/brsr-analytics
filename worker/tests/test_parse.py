from decimal import Decimal

import pytest

from api.app.services.units import convert_unit
from worker.parse.embeddings import hash_embedding
from worker.parse.pdf import detect_table_regions, locate_brsr_sections, parse_pdf
from worker.parse.xbrl import parse_xbrl


@pytest.mark.parametrize(
    ("value", "source", "expected", "unit"),
    [
        ("1000", "kWh", Decimal("3.6000"), "GJ"),
        ("2", "MWh", Decimal("7.2"), "GJ"),
        ("1.5", "ML", Decimal("1500.0"), "KL"),
        ("1250", "kgCO2e", Decimal("1.250"), "tCO2e"),
    ],
)
def test_unit_conversions_match_hand_values(
    value: str, source: str, expected: Decimal, unit: str
) -> None:
    assert convert_unit(value, source) == (expected, unit)


def test_xbrl_maps_context_units_and_exact_facts() -> None:
    content = b"""<?xml version='1.0'?>
    <xbrli:xbrl xmlns:xbrli='http://www.xbrl.org/2003/instance'
      xmlns:brsr='https://brsrlens.example/taxonomy' xmlns:iso4217='urn:iso'>
      <xbrli:context id='FY24'><xbrli:period><xbrli:startDate>2023-04-01</xbrli:startDate>
      <xbrli:endDate>2024-03-31</xbrli:endDate></xbrli:period></xbrli:context>
      <xbrli:unit id='U1'><xbrli:measure>iso4217:kWh</xbrli:measure></xbrli:unit>
      <brsr:BRSR_p6_e1_energy_total_gj contextRef='FY24' unitRef='U1'
       decimals='2'>1,000</brsr:BRSR_p6_e1_energy_total_gj>
      <brsr:BRSR_a_basics_company_name contextRef='FY24'>
      Alpha Limited</brsr:BRSR_a_basics_company_name>
    </xbrli:xbrl>"""
    facts = parse_xbrl(
        content,
        {
            "BRSR_p6_e1_energy_total_gj": ("p6.e1.energy_total_gj", "GJ"),
            "BRSR_a_basics_company_name": ("a.basics.company_name", None),
        },
    )
    assert [(fact.field_key, fact.value_raw) for fact in facts] == [
        ("p6.e1.energy_total_gj", "1,000"),
        ("a.basics.company_name", "Alpha Limited"),
    ]
    assert facts[0].value_num == Decimal("3.6000")
    assert facts[0].unit == "GJ"
    assert facts[0].period_end and facts[0].period_end.isoformat() == "2024-03-31"


@pytest.mark.parametrize(
    "pages",
    [
        [
            "Cover",
            "BUSINESS RESPONSIBILITY AND SUSTAINABILITY REPORT SECTION A General Disclosures",
            "PRINCIPLE 6 Environment",
        ],
        [
            "Annual report content. SECTION A: General Disclosures begins mid-page",
            "Principle 1 Integrity",
            "Principle 6 Environment",
        ],
        [
            "Cover",
            "Business Responsibility & Sustainability",
            "SECTION A General Disclosures",
            "Employee well-being Principle 3",
        ],
        [
            "Contents",
            "General disclosures - Section A",
            "Human Rights Principle Five",
            "PRINCIPLE 9 consumer value",
        ],
    ],
)
def test_section_locator_finds_messy_brsr_blocks(pages: list[str]) -> None:
    location = locate_brsr_sections(pages)
    assert location.start_page >= 1
    assert location.confidence >= 0.49
    assert location.page_sections


def test_section_locator_exposes_ambiguous_trap() -> None:
    pages = [
        "Contents: SECTION A General Disclosures",
        "Financial statements",
        "SECTION A General Disclosures",
        "PRINCIPLE 1 Integrity",
    ]
    assert locate_brsr_sections(pages).ambiguous is True


def test_table_candidate_detection_requires_aligned_rows_and_columns() -> None:
    words = []
    for row, y in enumerate((10.0, 20.0, 30.0)):
        for column, x in enumerate((10.0, 100.0, 200.0)):
            words.append((x, y, x + 30, y + 5, f"{row}-{column}", 0))
    region = detect_table_regions(words)[0]
    assert region.rows == 3
    assert region.columns >= 3


def test_hash_embeddings_are_repeatable_and_normalised() -> None:
    first = hash_embedding("energy intensity declined")
    assert first == hash_embedding("energy intensity declined")
    assert sum(value * value for value in first) == pytest.approx(1.0)


def test_pymupdf_pipeline_renders_150_dpi_pages() -> None:
    import fitz  # type: ignore[import-untyped]

    document = fitz.open()
    for text in (
        "Annual Report",
        "BUSINESS RESPONSIBILITY AND SUSTAINABILITY REPORT\nSECTION A General Disclosures",
        "PRINCIPLE 6 Environment\nTotal energy consumption was 1,000 GJ.",
    ):
        page = document.new_page()
        page.insert_text((72, 72), text)
    content = document.tobytes()
    document.close()
    pages, location = parse_pdf(content)
    assert location.start_page == 2
    assert len(pages) == 2
    assert pages[0].image_png.startswith(b"\x89PNG")
    # A4 at 150 dpi is approximately 1240 px wide.
    pixmap = fitz.Pixmap(pages[0].image_png)
    assert 1230 <= pixmap.width <= 1250
