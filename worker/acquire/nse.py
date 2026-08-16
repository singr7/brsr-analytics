from __future__ import annotations

import csv
import io
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.app.core.config import Settings
from api.app.models import (
    Company,
    Filing,
    FilingPage,
    IngestionRun,
    IngestionState,
    LibraryExemplar,
    LibraryPattern,
)
from api.app.services.acquisition import store_filing
from api.app.services.storage import ObjectStore
from worker.acquire.adapters import AcquisitionDisabledError, PoliteRateLimiter
from worker.parse.service import parse_filing

NSE_SOURCE = "nse_brsr"
LEGACY_SYNTHETIC_TICKERS = frozenset(
    {
        "ASTSTEEL", "BEACEM", "CEDCHEM", "DELMOT", "EONMOB", "FLUXPH", "GRNHOSP",
        "HELPOW", "IONREN", "JADETXT", "KITEFOOD", "LUMRET", "MERMIN", "NOVALOY",
        "ORCLAB", "PRIPOLY", "QUAENE", "RIVPAPR", "SOLAPP", "TERTYRE",
    }
)


@dataclass(frozen=True, slots=True)
class RegistryCompany:
    name: str
    industry: str
    symbol: str
    isin: str


@dataclass(frozen=True, slots=True)
class NseBRSRFiling:
    company_name: str
    symbol: str
    fy_from: int
    fy_to: int
    xbrl_url: str
    pdf_url: str | None
    submission_date: date
    revision_date: date | None


Transport = Callable[[str], httpx.Response]


def _parse_nse_date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text or text == "-":
        return None
    return datetime.strptime(text, "%d-%b-%Y").date()


def parse_registry_csv(content: str) -> list[RegistryCompany]:
    rows = csv.DictReader(io.StringIO(content.lstrip("\ufeff")))
    companies: list[RegistryCompany] = []
    for row in rows:
        symbol = (row.get("Symbol") or "").strip()
        isin = (row.get("ISIN Code") or "").strip()
        if symbol and isin:
            companies.append(
                RegistryCompany(
                    name=(row.get("Company Name") or symbol).strip(),
                    industry=(row.get("Industry") or "Unclassified").strip(),
                    symbol=symbol,
                    isin=isin,
                )
            )
    return companies


def parse_portal_response(payload: object, symbol: str, target_fy: int) -> NseBRSRFiling | None:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("NSE BRSR portal returned an unexpected response")
    candidates: list[NseBRSRFiling] = []
    for item in payload["data"]:
        if not isinstance(item, dict) or str(item.get("symbol", "")).upper() != symbol.upper():
            continue
        if int(item.get("fyTo", 0)) != target_fy or not item.get("xbrlFile"):
            continue
        submission = _parse_nse_date(item.get("submissionDate"))
        if submission is None:
            continue
        candidates.append(
            NseBRSRFiling(
                company_name=str(item.get("companyName") or symbol).strip(),
                symbol=symbol,
                fy_from=int(item.get("fyFrom", target_fy - 1)),
                fy_to=target_fy,
                xbrl_url=str(item["xbrlFile"]),
                pdf_url=str(item["attachmentFile"]) if item.get("attachmentFile") else None,
                submission_date=submission,
                revision_date=_parse_nse_date(item.get("revisionDate")),
            )
        )
    return max(
        candidates,
        key=lambda item: (item.revision_date or item.submission_date, item.submission_date),
        default=None,
    )


class NseBRSRClient:
    def __init__(
        self,
        settings: Settings,
        *,
        transport: Transport | None = None,
    ) -> None:
        if not settings.source_nse_brsr_enabled:
            raise AcquisitionDisabledError(
                "Source nse_brsr is disabled; approve the legal gate and set "
                "SOURCE_NSE_BRSR_ENABLED=true"
            )
        self.settings = settings
        self.transport = transport or self._get
        self.limiter = PoliteRateLimiter(settings.acquisition_rate_per_second)

    def _get(self, url: str) -> httpx.Response:
        last_error: httpx.HTTPError | None = None
        for _attempt in range(3):
            try:
                return httpx.get(
                    url,
                    timeout=60,
                    follow_redirects=True,
                    trust_env=False,
                    headers={
                        "User-Agent": self.settings.nse_brsr_user_agent,
                        "From": self.settings.nse_brsr_contact,
                        "Accept": "application/json,text/csv,application/xml;q=0.9,*/*;q=0.8",
                        "Connection": "close",
                        "Referer": "https://www.nseindia.com/companies-listing/"
                        "corporate-filings-bussiness-sustainabilitiy-reports",
                    },
                )
            except httpx.HTTPError as exc:
                last_error = exc
        if last_error is None:  # pragma: no cover - loop contract
            raise RuntimeError("NSE request retry loop did not execute")
        raise last_error

    def _request(self, url: str) -> httpx.Response:
        self.limiter.wait()
        response = self.transport(url)
        response.raise_for_status()
        return response

    def registry(self) -> list[RegistryCompany]:
        return parse_registry_csv(self._request(self.settings.nse_nifty50_registry_url).text)

    def discover(self, symbol: str, target_fy: int) -> NseBRSRFiling | None:
        from_date = date(target_fy, 4, 1).strftime("%d-%m-%Y")
        to_date = date(target_fy + 1, 3, 31).strftime("%d-%m-%Y")
        response = self._request(
            f"{self.settings.nse_brsr_portal_url}?symbol={quote(symbol, safe='')}"
            f"&from_date={from_date}&to_date={to_date}"
        )
        return parse_portal_response(response.json(), symbol, target_fy)

    def download_xbrl(self, filing: NseBRSRFiling) -> bytes:
        parsed = urlparse(filing.xbrl_url)
        if parsed.scheme != "https" or parsed.hostname != "nsearchives.nseindia.com":
            raise ValueError("NSE filing URL is not on the approved archive host")
        content = self._request(filing.xbrl_url).content
        if not content.lstrip().startswith(b"<?xml"):
            raise ValueError("NSE XBRL response is not an XML instance")
        return content


async def remove_legacy_synthetic_corpus(session: AsyncSession) -> int:
    companies = (
        await session.scalars(select(Company).where(Company.ticker.in_(LEGACY_SYNTHETIC_TICKERS)))
    ).all()
    company_ids = [company.id for company in companies]
    if company_ids:
        synthetic_pages = (
            select(FilingPage.id)
            .join(Filing, Filing.id == FilingPage.filing_id)
            .where(Filing.company_id.in_(company_ids))
        )
        pattern_ids = list(
            await session.scalars(
                select(LibraryExemplar.pattern_id).where(
                    LibraryExemplar.filing_page_id.in_(synthetic_pages)
                )
            )
        )
        await session.execute(
            delete(LibraryExemplar).where(LibraryExemplar.filing_page_id.in_(synthetic_pages))
        )
        if pattern_ids:
            await session.execute(delete(LibraryPattern).where(LibraryPattern.id.in_(pattern_ids)))
    for company in companies:
        await session.delete(company)
    await session.commit()
    return len(companies)


async def _upsert_registry_company(
    session: AsyncSession, registry: RegistryCompany
) -> Company:
    company = await session.scalar(select(Company).where(Company.ticker == registry.symbol))
    if company is None:
        company = Company(
            cin=registry.isin,
            name=registry.name,
            ticker=registry.symbol,
            exchange="NSE",
            sector=registry.industry,
            industry=registry.industry,
            mcap_band="large",
            ir_url=None,
        )
    else:
        company.name = registry.name
        company.sector = registry.industry
        company.industry = registry.industry
        company.mcap_band = "large"
    session.add(company)
    await session.commit()
    await session.refresh(company)
    return company


async def _record_missing(session: AsyncSession, company: Company, target_fy: int) -> None:
    filing = await session.scalar(
        select(Filing).where(Filing.company_id == company.id, Filing.fy == target_fy)
    )
    if filing is None:
        filing = Filing(company_id=company.id, fy=target_fy, source="xbrl")
    filing.status = "missing"
    filing.source_adapter = NSE_SOURCE
    filing.acquisition_attempts = (filing.acquisition_attempts or 0) + 1
    filing.acquisition_error = None
    session.add(filing)
    await session.commit()


async def ingest_nse_batch(
    session: AsyncSession,
    store: ObjectStore,
    settings: Settings,
    *,
    mode: str,
    target_fy: int,
    limit: int,
    start: int | None = None,
    replace_synthetic: bool = False,
    client: NseBRSRClient | None = None,
) -> IngestionRun:
    if mode not in {"initial", "next", "refresh"}:
        raise ValueError("mode must be initial, next, or refresh")
    portal = client or NseBRSRClient(settings)
    registry = portal.registry()
    state = await session.get(IngestionState, NSE_SOURCE)
    if state is None:
        state = IngestionState(source=NSE_SOURCE, next_offset=0, state_json={})
        session.add(state)
        await session.commit()
    if replace_synthetic:
        await remove_legacy_synthetic_corpus(session)
    offset = start if start is not None else (state.next_offset if mode == "next" else 0)
    if mode == "refresh":
        registered_symbols = set(await session.scalars(select(Company.ticker)))
        selected = [item for item in registry if item.symbol in registered_symbols][:limit]
        offset = 0
    else:
        selected = registry[offset : offset + limit]
    run = IngestionRun(
        source=NSE_SOURCE,
        mode=mode,
        status="running",
        target_fy=target_fy,
        batch_start=offset,
        requested_count=limit,
        discovered_count=len(selected),
        started_at=datetime.now(UTC),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    errors: list[str] = []
    for registry_company in selected:
        try:
            company = await _upsert_registry_company(session, registry_company)
            discovered = portal.discover(company.ticker, target_fy)
            if discovered is None:
                await _record_missing(session, company, target_fy)
                run.missing_count += 1
                continue
            content = portal.download_xbrl(discovered)
            filename = Path(urlparse(discovered.xbrl_url).path).name or (
                f"{company.ticker}-{target_fy}.xml"
            )
            filing, _ = await store_filing(
                session,
                store,
                company=company,
                fy=target_fy,
                filename=filename,
                content=content,
                source="xbrl",
                source_adapter=NSE_SOURCE,
                source_url=discovered.xbrl_url,
            )
            filing.submission_date = discovered.submission_date
            filing.revision_date = discovered.revision_date
            await session.commit()
            run.fetched_count += 1
            await parse_filing(
                session,
                store,
                filing.id,
                embedding_model=settings.embedding_model,
            )
            run.parsed_count += 1
        except Exception as exc:
            await session.rollback()
            run.error_count += 1
            errors.append(f"{registry_company.symbol}: {str(exc)[:240]}")
        finally:
            session.add(run)
            await session.commit()
    if mode in {"initial", "next"}:
        state.next_offset = offset + len(selected)
        state.state_json = {"registry_size": len(registry), "target_fy": target_fy}
        session.add(state)
    run.status = "completed_with_errors" if errors else "completed"
    run.error_summary = "\n".join(errors) or None
    run.completed_at = datetime.now(UTC)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run
