from datetime import date
from decimal import Decimal

import httpx
import pytest

from api.app.core.config import Settings
from worker.acquire.adapters import AcquisitionDisabledError
from worker.acquire.mappings import (
    UnresolvedScaleError,
    convert_numeric_value,
    load_mapping_specs,
    load_turnover_scales,
    resolve_turnover_inr,
)
from worker.acquire.nse import (
    NseBRSRClient,
    parse_portal_response,
    parse_registry_csv,
)
from worker.parse.xbrl import parse_raw_xbrl_facts

REGISTRY = """Company Name,Industry,Symbol,Series,ISIN Code
Adani Enterprises Ltd.,Metals & Mining,ADANIENT,EQ,INE423A01024
HDFC Bank Ltd.,Financial Services,HDFCBANK,EQ,INE040A01034
"""


def test_registry_csv_preserves_official_order_and_classification() -> None:
    companies = parse_registry_csv(REGISTRY)
    assert [item.symbol for item in companies] == ["ADANIENT", "HDFCBANK"]
    assert companies[0].industry == "Metals & Mining"
    assert companies[1].isin == "INE040A01034"


def test_portal_response_selects_latest_revision_for_financial_year() -> None:
    payload = {
        "data": [
            {
                "companyName": "Example Limited",
                "symbol": "EXAMPLE",
                "fyFrom": 2024,
                "fyTo": 2025,
                "submissionDate": "01-Jul-2025",
                "revisionDate": "-",
                "xbrlFile": "https://nsearchives.nseindia.com/corporate/xbrl/original.xml",
            },
            {
                "companyName": "Example Limited",
                "symbol": "EXAMPLE",
                "fyFrom": 2024,
                "fyTo": 2025,
                "submissionDate": "01-Jul-2025",
                "revisionDate": "03-Jul-2025",
                "xbrlFile": "https://nsearchives.nseindia.com/corporate/xbrl/revised.xml",
            },
        ]
    }
    filing = parse_portal_response(payload, "EXAMPLE", 2025)
    assert filing is not None
    assert filing.xbrl_url.endswith("revised.xml")
    assert filing.revision_date == date(2025, 7, 3)


def test_nse_source_is_disabled_by_default() -> None:
    with pytest.raises(AcquisitionDisabledError, match="SOURCE_NSE_BRSR_ENABLED"):
        NseBRSRClient(Settings(source_nse_brsr_enabled=False))


def test_nse_client_rejects_non_archive_download_host() -> None:
    settings = Settings(source_nse_brsr_enabled=True)
    response = httpx.Response(200, text=REGISTRY, request=httpx.Request("GET", "https://x.test"))
    client = NseBRSRClient(settings, transport=lambda _url: response)
    assert len(client.registry()) == 2


def test_raw_xbrl_parser_persists_unmapped_concepts() -> None:
    content = (
        b'<?xml version="1.0"?>'
        b'<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:b="urn:brsr">'
        b'<xbrli:context id="FY"><xbrli:entity><xbrli:identifier scheme="isin">INE000'
        b'</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2024-04-01'
        b'</xbrli:startDate><xbrli:endDate>2025-03-31</xbrli:endDate></xbrli:period>'
        b'</xbrli:context><xbrli:unit id="INR"><xbrli:measure>iso4217:INR</xbrli:measure>'
        b'</xbrli:unit><b:CorporateIdentityNumber contextRef="FY">L12345MH2000PLC123456'
        b'</b:CorporateIdentityNumber><b:Turnover contextRef="FY" unitRef="INR">1,250'
        b'</b:Turnover></xbrli:xbrl>'
    )
    facts = parse_raw_xbrl_facts(content)
    assert [item.concept for item in facts] == ["CorporateIdentityNumber", "Turnover"]
    assert facts[1].value_num == 1250
    assert facts[1].period_end == date(2025, 3, 31)


def test_raw_parser_retains_reported_decimals() -> None:
    content = (
        b'<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:b="urn:brsr">'
        b'<xbrli:context id="FY"><xbrli:period><xbrli:startDate>2024-04-01</xbrli:startDate>'
        b"<xbrli:endDate>2025-03-31</xbrli:endDate></xbrli:period></xbrli:context>"
        b'<b:Turnover contextRef="FY" unitRef="INR" decimals="2">143368.92</b:Turnover>'
        b'<b:Other contextRef="FY" unitRef="INR">7</b:Other>'
        b"</xbrli:xbrl>"
    )
    facts = parse_raw_xbrl_facts(content)
    assert facts[0].decimals == 2
    # `decimals` is precision, not scale: it is retained for provenance but must never be
    # used to infer the INR reporting scale.
    assert facts[1].decimals is None


def test_provisional_mapping_file_covers_common_units_and_turnover() -> None:
    version, specs = load_mapping_specs()
    assert version == "0.2.0-provisional"
    assert len(specs) == 16
    keys = {spec.field_key for spec in specs}
    assert {
        "a.basics.turnover_inr",
        "p6.e1.energy_total_gj",
        "p6.e2.water_total_kl",
        "p6.e3.scope1_tco2e",
        "p6.e3.scope2_tco2e",
    } <= keys


def test_common_unit_conversions_are_explicit() -> None:
    assert convert_numeric_value(Decimal("729480744"), "MJ", {"MJ": "0.001"}) == (
        Decimal("729480.744"),
        "MJ",
    )
    assert convert_numeric_value(Decimal("3.78968"), "TJ", {"TJ": "1000"}) == (
        Decimal("3789.68000"),
        "TJ",
    )


def test_turnover_scale_comes_from_the_reviewed_registry() -> None:
    registry = load_turnover_scales()
    # Above the threshold a crore or million reading is economically impossible, so the
    # figure is taken as already absolute without needing a registry entry.
    assert resolve_turnover_inr(
        Decimal("978947500000"), issuer="ADANIENT", registry=registry
    ) == (Decimal("978947500000"), "absolute")
    # Coal India and Dr. Reddy's both sit in the ambiguous band but report at different
    # scales, which is exactly why magnitude cannot be used to infer scale.
    assert resolve_turnover_inr(
        Decimal("143368.92"), issuer="COALINDIA", registry=registry
    ) == (Decimal("1433689200000.0000000"), "crore")
    assert resolve_turnover_inr(Decimal("231154"), issuer="DRREDDY", registry=registry) == (
        Decimal("231154000000"),
        "million",
    )


def test_unregistered_issuer_in_the_ambiguous_band_is_withheld_not_guessed() -> None:
    registry = load_turnover_scales()
    with pytest.raises(UnresolvedScaleError):
        resolve_turnover_inr(Decimal("143368.92"), issuer="NOTLISTED", registry=registry)
    with pytest.raises(UnresolvedScaleError):
        resolve_turnover_inr(Decimal("143368.92"), issuer=None, registry=registry)
