from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from api.app.core.config import Settings
from api.app.models import Company, Filing
from api.app.services.acquisition import store_filing, validate_artifact
from api.app.services.storage import LocalObjectStore, raw_filing_key
from worker.acquire.adapters import (
    AcquisitionDisabledError,
    CompanyIRAdapter,
    CompanyRef,
    ExchangeXbrlAdapter,
)

FIXTURES = Path("testdata/acquisition")


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def response(url: str, body: bytes, etag: str = '"v1"') -> httpx.Response:
    return httpx.Response(
        200,
        content=body,
        headers={"content-type": "application/xml", "etag": etag},
        request=httpx.Request("GET", url),
    )


def test_all_automated_sources_default_disabled() -> None:
    settings = Settings()
    assert not settings.source_exchange_xbrl_enabled
    assert not settings.source_exchange_announcements_enabled
    assert not settings.source_company_ir_enabled
    adapter = ExchangeXbrlAdapter(
        enabled=settings.source_exchange_xbrl_enabled,
        rate_per_second=1,
        url_template="https://example.test/{ticker}/{fy}",
    )
    with pytest.raises(AcquisitionDisabledError, match="legal review"):
        adapter.fetch(CompanyRef("CIN", "ABC", "NSE"), 2024)


def test_adapter_rate_limit_checksum_and_resume_cursor() -> None:
    clock = FakeClock()
    body = (FIXTURES / "alpha-2024.xbrl").read_bytes()
    adapter = ExchangeXbrlAdapter(
        enabled=True,
        rate_per_second=0.5,
        url_template="https://example.test/{ticker}/{fy}",
        clock=clock,
        transport=lambda url: response(url, body),
    )
    company = CompanyRef("CIN", "ABC", "NSE")
    first = adapter.fetch(company, 2024, {"page": 2})
    second = adapter.fetch(company, 2024, first.cursor)

    assert clock.sleeps == [2.0]
    assert first.checksum_sha256 == second.checksum_sha256
    assert second.cursor == {"page": 2, "etag": '"v1"'}
    assert second.filename == "ABC-2024.xbrl"


def test_company_ir_adapter_discovers_link_then_resumes_directly() -> None:
    clock = FakeClock()
    requests: list[str] = []
    pdf = (FIXTURES / "alpha-2024.pdf").read_bytes()

    def transport(url: str) -> httpx.Response:
        requests.append(url)
        body = (
            b'<html><a href="/reports/brsr-2023-24.pdf">BRSR 2024</a></html>'
            if url.endswith("/investors")
            else pdf
        )
        media_type = "text/html" if url.endswith("/investors") else "application/pdf"
        return httpx.Response(
            200,
            content=body,
            headers={"content-type": media_type},
            request=httpx.Request("GET", url),
        )

    adapter = CompanyIRAdapter(enabled=True, rate_per_second=1, clock=clock, transport=transport)
    company = CompanyRef("CIN", "ABC", "NSE", "https://company.test/investors")
    first = adapter.fetch(company, 2024)
    resumed = adapter.fetch(company, 2024, first.cursor)

    assert first.status == "fetched"
    assert first.cursor["artifact_url"] == "https://company.test/reports/brsr-2023-24.pdf"
    assert requests == [
        "https://company.test/investors",
        "https://company.test/reports/brsr-2023-24.pdf",
        "https://company.test/reports/brsr-2023-24.pdf",
    ]
    assert resumed.checksum_sha256 == first.checksum_sha256
    assert clock.sleeps == [1.0, 1.0]


@pytest.mark.parametrize("path", sorted(FIXTURES.iterdir()), ids=lambda path: path.name)
def test_six_synthetic_artifacts_validate_and_store(path: Path, tmp_path: Path) -> None:
    content = path.read_bytes()
    artifact_type, media_type = validate_artifact(path.name, content)
    store = LocalObjectStore(str(tmp_path), "fixtures")
    key = raw_filing_key("L00001MH2000PLC000001", 2024, path.name)
    uri = store.put(key, content, media_type)

    assert artifact_type in {"pdf", "xbrl"}
    assert uri == f"s3://fixtures/{key}"
    assert (tmp_path / "fixtures" / key).read_bytes() == content


def test_artifact_validation_rejects_extension_spoof() -> None:
    with pytest.raises(ValueError, match="does not match"):
        validate_artifact("not-really.pdf", b"<xml />")


class FakeSession:
    def __init__(self) -> None:
        self.filing: Filing | None = None

    async def scalar(self, statement: object) -> Filing | None:
        del statement
        return self.filing

    def add(self, instance: object) -> None:
        if isinstance(instance, Filing):
            if instance.id is None:
                instance.id = uuid4()
            self.filing = instance

    async def commit(self) -> None:
        return None

    async def refresh(self, instance: object) -> None:
        del instance


async def test_manual_upload_creates_filing_object_and_deduplicates(tmp_path: Path) -> None:
    company = Company(
        id=uuid4(),
        cin="L00001MH2000PLC000001",
        name="Alpha Limited",
        ticker="ALPHA",
        exchange="NSE",
        sector="Energy & Utilities",
        industry="Power",
        mcap_band="large",
        ir_url=None,
    )
    session = FakeSession()
    store = LocalObjectStore(str(tmp_path), "filings")
    content = (FIXTURES / "alpha-2024.pdf").read_bytes()

    filing, first = await store_filing(
        session,  # type: ignore[arg-type]
        store,
        company=company,
        fy=2024,
        filename="alpha-2024.pdf",
        content=content,
        source="manual",
        source_adapter="manual_upload",
    )
    repeated, second = await store_filing(
        session,  # type: ignore[arg-type]
        store,
        company=company,
        fy=2024,
        filename="alpha-2024.pdf",
        content=content,
        source="manual",
        source_adapter="manual_upload",
    )

    assert filing.status == "fetched"
    assert filing.s3_raw == "s3://filings/raw/L00001MH2000PLC000001/2024/alpha-2024.pdf"
    assert filing.checksum_sha256 == first.checksum_sha256
    assert repeated.id == filing.id
    assert second.deduplicated
