# NSE BRSR ingestion and refresh operations

## What this module ingests

The production corpus uses two official NSE-published sources:

- NIFTY 50 registry CSV: `https://nsearchives.nseindia.com/content/indices/ind_nifty50list.csv`
- BRSR portal index: `https://www.nseindia.com/api/corporate-bussiness-sustainabilitiy`

The registry supplies company name, NSE symbol, industry and ISIN. The BRSR index supplies
the financial-year range, original submission date, revision date, PDF evidence URL and XBRL
evidence URL. The importer selects the latest revision for the requested `fyTo`, downloads the
XBRL only from `nsearchives.nseindia.com`, validates that it is XML, hashes it and stores the raw
artifact before parsing it.

The initial cohort is the first 25 rows in NSE's official NIFTY 50 CSV order. The persisted
`ingestion_state.next_offset` cursor then makes `next --limit 10` select rows 26–35. This is a
deterministic coverage policy, not a claim that the rows are ordered by current market cap.

## Seeded local corpus (2026-08-16)

FY 2024–25 (`fyTo=2025`) now covers **50 companies and 50 filings** with 109,789 persisted raw
XBRL facts, imported in two batches against the official NIFTY 50 registry order.

Batch 1 (`initial --limit 25`): 25 discovered, fetched and parsed, zero missing or errors.

`ADANIENT`, `ADANIPORTS`, `APOLLOHOSP`, `ASIANPAINT`, `AXISBANK`, `BAJAJ-AUTO`,
`BAJAJFINSV`, `BAJFINANCE`, `BEL`, `BHARTIARTL`, `CIPLA`, `COALINDIA`, `DRREDDY`,
`EICHERMOT`, `ETERNAL`, `GRASIM`, `HCLTECH`, `HDFCBANK`, `HDFCLIFE`, `HINDALCO`,
`HINDUNILVR`, `ICICIBANK`, `INDIGO`, `INFY`, and `ITC`.

Batch 2 (`next --limit 25 --publish`): 25 discovered, 24 fetched and parsed, 1 missing (no FY25
filing published at the portal for that symbol), zero errors.

`JIOFIN`, `JSWSTEEL`, `KOTAKBANK`, `LT`, `M&M`, `MARUTI`, `MAXHEALTH`, `NESTLEIND`, `NTPC`,
`ONGC`, `POWERGRID`, `RELIANCE`, `SBILIFE`, `SBIN`, `SHRIRAMFIN`, `SUNPHARMA`, `TATACONSUM`,
`TATASTEEL`, `TCS`, `TECHM`, `TITAN`, `TMPV`, `TRENT`, `ULTRACEMCO`, and `WIPRO`.

Batch 2 reported `withheld=1`: `JIOFIN` reports turnover below the absolute threshold and had no
entry in the reviewed `turnover_scale` registry, so it was correctly withheld rather than guessed.
A reviewed entry was then added at confidence 0.70 and the batch republished at `withheld=0`. This
is the expected workflow for every new issuer that reports below the threshold.

Only filings parsed after migration `0011` carry `xbrl_facts.decimals`; batch 1 rows remain null
until that cohort is re-ingested.

This list describes the checked local database state, not a portable data fixture: raw NSE
artifacts and database rows are deliberately not committed to Git. Re-running the initial command
reconstructs the corpus from the official sources.

## Legal and source gate

Automated access remains fail-closed. Record approval in `docs/gates/legal.md`, set a monitored
contact in `NSE_BRSR_CONTACT`, and then set:

```dotenv
SOURCE_NSE_BRSR_ENABLED=true
```

Disabling the flag prevents new portal requests but never deletes retained evidence or parsed
facts. Rate is globally controlled by `ACQUISITION_RATE_PER_SECOND` (default `0.5`, one request
every two seconds).

## Local commands

Host environment with `uv`:

```sh
make migrate
make seed
make ingest-nse-initial NSE_FY=2025
make ingest-nse-next NSE_FY=2025 NSE_LIMIT=10
make ingest-nse-refresh NSE_FY=2025
make publish-nse NSE_FY=2025
```

Docker equivalent (include the local compose override when ports differ):

```sh
docker compose exec api python -m alembic upgrade head
docker compose exec api python -m api.app.db.seed
docker compose exec api python -m worker.acquire.cli initial --fy 2025 --limit 25 --replace-synthetic --publish
docker compose exec api python -m worker.acquire.cli next --fy 2025 --limit 10 --publish
docker compose exec api python -m worker.acquire.cli refresh --fy 2025 --limit 10 --publish
```

`initial --replace-synthetic` removes only the 20 legacy fictional ticker records. It does not
delete manual uploads or other real companies. `next` advances the persisted registry cursor.
`refresh` revisits registered companies without advancing it and replaces a company-FY artifact
only when the official XBRL checksum changes.

## Scheduled refresh

Celery Beat registers the refresh task only when scheduling is enabled:

```dotenv
NSE_BRSR_SCHEDULE_ENABLED=true
NSE_BRSR_REFRESH_HOURS=168
NSE_BRSR_DEFAULT_FY=2025
NSE_BRSR_DEFAULT_BATCH_SIZE=10
```

Restart `scheduler` and `worker` after changing these values. The default is weekly (`168`
hours, and each scheduled run uses `NSE_BRSR_DEFAULT_BATCH_SIZE`. Every run is written to
`ingestion_runs` with requested, discovered, fetched, parsed,
missing and error counts. A failed company does not abort the remaining batch.

## Persistence and lineage

- `companies`: official company name, symbol, NSE industry/sector and ISIN; the CIN replaces the
  temporary ISIN identifier after the XBRL `CorporateIdentityNumber` fact is parsed.
- `filings`: one company/FY artifact, NSE URL, checksum, submission/revision dates and pipeline
  status.
- object storage: immutable raw XBRL under `raw/{identifier}/{fy}/{filename}`.
- `xbrl_facts`: lossless persistence of every reported concept, raw/numeric value, unit,
  context, period and dimensional members.
- `extracted_fields`: governed mappings into BRSR Lens's semantic field catalog when an NSE
  concept mapping exists.
- `ingestion_state`: the next NIFTY registry offset.
- `ingestion_runs`: auditable manual and scheduled run outcomes.

The checked-in semantic taxonomy began as a placeholder and does not map all live NSE concepts.
Raw facts are retained even when `mapped_field_count` is zero. Only mappings declared in the
versioned provisional registry can be pinned by `--publish`; all other facts remain unpublished.

The FY25 mapping/review layer is documented in
`docs/operations/NSE_METRIC_MAPPING_REVIEW.md`. It publishes a deliberately small set of explicit
common-unit and turnover-normalized metrics with Admin-visible assumptions; it does not imply
domain approval.

## Admin dashboard

Sign in with a platform-admin account and open `/admin/ingestion`. The dashboard shows:

- source/scheduler state, refresh interval, default FY and next cohort offset;
- total companies, filings, parsed filings and raw XBRL facts;
- company name/symbol, sector, industry, FY, status, submission date, fact counts and original
  NSE XBRL evidence link;
- the ten most recent ingestion runs and their error/missing totals.

## Refresh checklist

1. Confirm the source gate and monitored User-Agent contact remain current.
2. Set `NSE_BRSR_DEFAULT_FY` to the financial year ending year required by the portal (`fyTo`).
3. Run a one-company canary using `initial --start 0 --limit 1`.
4. Check `/admin/ingestion` for a parsed filing and non-zero raw facts.
5. Run the intended cohort or enable the scheduler.
6. Review run errors and source revisions before QA/publishing.
