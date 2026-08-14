from __future__ import annotations

import hashlib
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Protocol
from urllib.parse import urljoin

import httpx


class AcquisitionDisabledError(RuntimeError):
    pass


class Clock(Protocol):
    def monotonic(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...


class SystemClock:
    monotonic = staticmethod(time.monotonic)
    sleep = staticmethod(time.sleep)


@dataclass(frozen=True, slots=True)
class CompanyRef:
    cin: str
    ticker: str
    exchange: str
    ir_url: str | None = None


@dataclass(frozen=True, slots=True)
class FetchResult:
    status: str
    cursor: dict[str, object]
    content: bytes | None = None
    filename: str | None = None
    media_type: str | None = None
    source_url: str | None = None
    checksum_sha256: str | None = None

    @classmethod
    def missing(cls, cursor: dict[str, object]) -> FetchResult:
        return cls(status="missing", cursor=cursor)


class PoliteRateLimiter:
    def __init__(self, rate_per_second: float, clock: Clock | None = None) -> None:
        if rate_per_second <= 0:
            raise ValueError("rate_per_second must be positive")
        self.interval = 1 / rate_per_second
        self.clock = clock or SystemClock()
        self.last_request_at: float | None = None

    def wait(self) -> None:
        now = self.clock.monotonic()
        if self.last_request_at is not None:
            remaining = self.interval - (now - self.last_request_at)
            if remaining > 0:
                self.clock.sleep(remaining)
        self.last_request_at = self.clock.monotonic()


Transport = Callable[[str], httpx.Response]


class SourceAdapter(ABC):
    """Adapter contract. A source must remain disabled until its SOURCES.md gate is signed."""

    name: str
    artifact_type: str

    def __init__(
        self,
        *,
        enabled: bool,
        rate_per_second: float,
        transport: Transport | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.enabled = enabled
        self.limiter = PoliteRateLimiter(rate_per_second, clock)
        self.transport = transport or self._http_get

    def fetch(
        self, company: CompanyRef, fy: int, cursor: dict[str, object] | None = None
    ) -> FetchResult:
        if not self.enabled:
            raise AcquisitionDisabledError(f"Source {self.name} is disabled pending legal review")
        self.limiter.wait()
        url = self.build_url(company, fy, cursor or {})
        response = self.transport(url)
        next_cursor = self.next_cursor(response, cursor or {})
        if response.status_code == 404:
            return FetchResult.missing(next_cursor)
        response.raise_for_status()
        content = response.content
        filename = self.filename(company, fy, response)
        return FetchResult(
            status="fetched",
            content=content,
            filename=filename,
            media_type=response.headers.get("content-type", "application/octet-stream"),
            source_url=str(response.url),
            checksum_sha256=hashlib.sha256(content).hexdigest(),
            cursor=next_cursor,
        )

    @staticmethod
    def _http_get(url: str) -> httpx.Response:
        return httpx.get(
            url,
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": "BRSRLensBot/0.1 (+legal-contact@brsrlens.local)"},
        )

    @abstractmethod
    def build_url(self, company: CompanyRef, fy: int, cursor: dict[str, object]) -> str: ...

    @abstractmethod
    def filename(self, company: CompanyRef, fy: int, response: httpx.Response) -> str: ...

    def next_cursor(
        self, response: httpx.Response, previous: dict[str, object]
    ) -> dict[str, object]:
        etag = response.headers.get("etag")
        return {**previous, "etag": etag} if etag else previous


class TemplatedAdapter(SourceAdapter):
    """Direct exchange endpoints; robots and reuse terms are unresolved, so default OFF."""

    url_template: str
    extension: str

    def __init__(self, *, url_template: str, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self.url_template = url_template

    def build_url(self, company: CompanyRef, fy: int, cursor: dict[str, object]) -> str:
        del cursor
        if not self.url_template:
            raise ValueError(f"URL template is not configured for {self.name}")
        return self.url_template.format(
            cin=company.cin, ticker=company.ticker, exchange=company.exchange, fy=fy
        )

    def filename(self, company: CompanyRef, fy: int, response: httpx.Response) -> str:
        del response
        return f"{company.ticker}-{fy}.{self.extension}"


class ExchangeXbrlAdapter(TemplatedAdapter):
    """Exchange XBRL endpoint. Automated use requires counsel approval; default OFF."""

    name = "exchange_xbrl"
    artifact_type = "xbrl"
    extension = "xbrl"


class ExchangeAnnouncementAdapter(TemplatedAdapter):
    """Exchange announcement PDF endpoint. Automated use requires approval; default OFF."""

    name = "exchange_announcements"
    artifact_type = "pdf"
    extension = "pdf"


class CompanyIRAdapter(SourceAdapter):
    """Company IR page adapter. Per-domain robots/terms review is required; default OFF."""

    name = "company_ir"
    artifact_type = "pdf"

    def fetch(
        self, company: CompanyRef, fy: int, cursor: dict[str, object] | None = None
    ) -> FetchResult:
        if not self.enabled:
            raise AcquisitionDisabledError(f"Source {self.name} is disabled pending legal review")
        if not company.ir_url:
            raise ValueError("Company has no reviewed IR page URL")
        previous = cursor or {}
        artifact_url = previous.get("artifact_url")
        if not isinstance(artifact_url, str):
            self.limiter.wait()
            page = self.transport(company.ir_url)
            page.raise_for_status()
            parser = FilingLinkParser()
            parser.feed(page.text)
            candidates = [
                urljoin(company.ir_url, href)
                for href, label in parser.links
                if "brsr" in f"{href} {label}".lower()
                and (str(fy) in f"{href} {label}" or str(fy - 1) in f"{href} {label}")
            ]
            if not candidates:
                return FetchResult.missing({**previous, "ir_page_checked": company.ir_url})
            artifact_url = candidates[0]
        self.limiter.wait()
        response = self.transport(artifact_url)
        next_cursor = self.next_cursor(response, {**previous, "artifact_url": artifact_url})
        if response.status_code == 404:
            return FetchResult.missing(next_cursor)
        response.raise_for_status()
        content = response.content
        return FetchResult(
            status="fetched",
            cursor=next_cursor,
            content=content,
            filename=self.filename(company, fy, response),
            media_type=response.headers.get("content-type", "application/pdf"),
            source_url=str(response.url),
            checksum_sha256=hashlib.sha256(content).hexdigest(),
        )

    def build_url(self, company: CompanyRef, fy: int, cursor: dict[str, object]) -> str:
        del fy, cursor
        if not company.ir_url:
            raise ValueError("Company has no reviewed IR page URL")
        return company.ir_url

    def filename(self, company: CompanyRef, fy: int, response: httpx.Response) -> str:
        del response
        return f"{company.ticker}-{fy}.pdf"


class FilingLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._label: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._label = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._label.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href:
            self.links.append((self._href, " ".join(self._label)))
            self._href = None
            self._label = []
