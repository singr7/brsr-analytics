from datetime import date

import httpx
import pytest

from api.app.core.config import Settings
from worker.acquire.adapters import AcquisitionDisabledError
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
