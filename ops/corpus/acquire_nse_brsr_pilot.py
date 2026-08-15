"""Acquire the governed 25-filing NSE BRSR pilot corpus.

The raw PDF/XML artifacts are written below .data/ (git-ignored). A compact,
checksummed provenance manifest is written to corpus/manifests/ and is safe to
commit. This is a deliberately bounded pilot, not the S19 1,000-company sweep.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

PORTAL_URL = (
    "https://www.nseindia.com/companies-listing/"
    "corporate-filings-bussiness-sustainabilitiy-reports"
)
API_URL = "https://www.nseindia.com/api/corporate-bussiness-sustainabilitiy"
DEFAULT_SYMBOLS = (
    "APOLLOHOSP",
    "ASIANPAINT",
    "BAJFINANCE",
    "BHARTIARTL",
    "COALINDIA",
    "DLF",
    "HDFCBANK",
    "HINDUNILVR",
    "ICICIBANK",
    "INFY",
    "JSWSTEEL",
    "LT",
    "MARUTI",
    "NIACL",
    "NTPC",
    "ONGC",
    "POWERGRID",
    "RAJESHEXPO",
    "RELIANCE",
    "SBIN",
    "SUNPHARMA",
    "TATAMOTORS",
    "TATASTEEL",
    "TCS",
    "ULTRACEMCO",
)
MANIFEST_FIELDS = (
    "symbol",
    "company_name",
    "fy_from",
    "fy_to",
    "submission_date",
    "revision_date",
    "source_portal_url",
    "source_api_url",
    "pdf_url",
    "xbrl_url",
    "pdf_path",
    "xbrl_path",
    "pdf_bytes",
    "xbrl_bytes",
    "pdf_sha256",
    "xbrl_sha256",
    "downloaded_at_utc",
    "status",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_filings(data: list[dict[str, Any]], symbols: tuple[str, ...]) -> list[dict[str, Any]]:
    by_symbol: dict[str, dict[str, Any]] = {}
    wanted = set(symbols)
    for filing in data:
        symbol = str(filing.get("symbol", "")).upper()
        if symbol not in wanted or filing.get("fyFrom") != 2024 or filing.get("fyTo") != 2025:
            continue
        if not filing.get("attachmentFile") or not filing.get("xbrlFile"):
            continue
        by_symbol[symbol] = filing
    missing = sorted(wanted - by_symbol.keys())
    if missing:
        raise RuntimeError(f"NSE response is missing requested FY 2024-25 filings: {missing}")
    return [by_symbol[symbol] for symbol in symbols]


def download(
    client: httpx.Client,
    url: str,
    destination: Path,
    *,
    expected: bytes,
    attempts: int,
) -> bool:
    if destination.is_file() and destination.stat().st_size > 0:
        prefix = destination.read_bytes()[: max(len(expected), 8)].lstrip()
        if prefix.startswith(expected):
            return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, attempts + 1):
        try:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                with destination.open("wb") as handle:
                    for chunk in response.iter_bytes(1024 * 1024):
                        handle.write(chunk)
            prefix = destination.read_bytes()[: max(len(expected), 8)].lstrip()
            if not prefix.startswith(expected):
                raise RuntimeError(f"Unexpected content at {url}")
            return True
        except (httpx.HTTPError, RuntimeError):
            destination.unlink(missing_ok=True)
            if attempt == attempts:
                raise
            time.sleep(2**attempt)


def write_manifest(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def run(args: argparse.Namespace) -> None:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 Chrome/127 Safari/537.36"
        ),
        "Accept": "application/json,text/html,application/xhtml+xml,application/xml,*/*",
    }
    interval = 1 / args.rate_per_second
    with httpx.Client(headers=headers, follow_redirects=True, timeout=120) as client:
        client.get(PORTAL_URL).raise_for_status()
        response = client.get(
            API_URL,
            params={"from_date": args.from_date, "to_date": args.to_date},
            headers={"Referer": PORTAL_URL},
        )
        response.raise_for_status()
        filings = select_filings(response.json()["data"], DEFAULT_SYMBOLS)
        rows: list[dict[str, object]] = []
        for index, filing in enumerate(filings, start=1):
            symbol = str(filing["symbol"]).upper()
            report_dir = args.output_root / symbol
            pdf_path = report_dir / "brsr.pdf"
            xbrl_path = report_dir / "brsr.xml"
            pdf_downloaded = download(
                client,
                str(filing["attachmentFile"]),
                pdf_path,
                expected=b"%PDF-",
                attempts=args.attempts,
            )
            if pdf_downloaded:
                time.sleep(interval)
            xbrl_downloaded = download(
                client,
                str(filing["xbrlFile"]),
                xbrl_path,
                expected=b"<",
                attempts=args.attempts,
            )
            if xbrl_downloaded:
                time.sleep(interval)
            downloaded_at = datetime.now(UTC).replace(microsecond=0).isoformat()
            rows.append(
                {
                    "symbol": symbol,
                    "company_name": filing["companyName"],
                    "fy_from": filing["fyFrom"],
                    "fy_to": filing["fyTo"],
                    "submission_date": filing["submissionDate"],
                    "revision_date": filing["revisionDate"],
                    "source_portal_url": PORTAL_URL,
                    "source_api_url": str(response.url),
                    "pdf_url": filing["attachmentFile"],
                    "xbrl_url": filing["xbrlFile"],
                    "pdf_path": pdf_path.as_posix(),
                    "xbrl_path": xbrl_path.as_posix(),
                    "pdf_bytes": pdf_path.stat().st_size,
                    "xbrl_bytes": xbrl_path.stat().st_size,
                    "pdf_sha256": sha256_file(pdf_path),
                    "xbrl_sha256": sha256_file(xbrl_path),
                    "downloaded_at_utc": downloaded_at,
                    "status": "downloaded",
                }
            )
            write_manifest(args.manifest, rows)
            print(f"[{index:02d}/{len(filings)}] {symbol}: PDF + XBRL verified", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-date", default="01-04-2025")
    parser.add_argument("--to-date", default="31-03-2026")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(".data/corpus/nse-brsr/fy2024-25"),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("corpus/manifests/nse_brsr_fy2024_25_pilot.csv"),
    )
    parser.add_argument("--rate-per-second", type=float, default=0.5)
    parser.add_argument("--attempts", type=int, default=3)
    args = parser.parse_args()
    if args.rate_per_second <= 0:
        parser.error("--rate-per-second must be positive")
    run(args)


if __name__ == "__main__":
    main()
