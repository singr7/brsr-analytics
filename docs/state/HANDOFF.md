# HANDOFF — after S04 (2026-08-14)

## Repo state: `main` · dev services up · migrations head `0003`

## Delivered

- Operator-supplied top-1,000 registry builder ranks market cap, validates CIN uniqueness,
  assigns large/mid/small bands, and maps NIC divisions via `taxonomy/sectors.yaml`.
- Default-OFF exchange XBRL, exchange-announcement PDF, and company-IR page adapters share
  a polite limiter, checksums, persistent per-source/company/FY cursors, and bounded retries.
- Raw PDF/XBRL artifacts use `raw/{cin}/{fy}/{filename}` with local-dev and signed S3
  backends; S3 writes request SSE-S3. Same-checksum company/FY uploads are idempotent.
- Platform-admin raw-body upload API and CLI provide the lawful manual/bulk fallback.
- `GET /api/admin/coverage?fy=YYYY` reports fetched/total and percentage overall and by
  sector × market-cap band. Both admin routes require an authenticated platform admin.
- Six constructed artifacts (2 XBRL, 4 PDF) exercise validation/storage offline; live API
  coverage/upload and PostgreSQL integrity suites passed against Compose.

## Contracts S05 relies on

- Models: `Filing` acquisition fields and `AcquisitionCursor` in `models/corpus.py`;
  statuses produced by acquisition are `fetched|missing|error`.
- Adapter interface: `SourceAdapter.fetch(CompanyRef, fy, cursor?) -> FetchResult` in
  `worker/acquire/adapters.py`; task is `worker.acquire.company_fy(company_id, fy, adapter)`.
- Storage: `ObjectStore.put(key, bytes, content_type) -> s3://...`; raw key helper is
  `raw_filing_key(cin, fy, filename)` in `services/storage.py`.
- Manual API: `PUT /api/admin/filings/{company_id}/{fy}`, octet-stream body plus
  `X-Filename`; CLI: `python -m worker.acquire.upload --company-id UUID --fy YYYY FILE`.
- Coverage: `GET /api/admin/coverage?fy=YYYY`; response groups on `sector,mcap_band`.
- Registry: `python ops/registry/build_registry.py INPUT.csv [--limit 1000] [--dry-run]`;
  required columns are documented in that script; optional `ir_url` is a reviewed IR page.
- Source governance and exact flag table: `worker/acquire/SOURCES.md`. All automated source
  flags default false and must remain false until source-specific legal approval.

## Sharp edges

- The S02 uniqueness contract permits one preferred raw filing per company/FY; a later
  different artifact replaces that row/object reference, while checksum repeats dedupe.
- IR discovery deliberately chooses the first FY-matching BRSR link; review `ir_url` inputs
  and cursor state when sites expose amended filings.
- Local object storage is for development only. Production must select `s3` and provide AWS
  credentials through the secret store; no bucket is public.
- Live S04 tests target FY 2199 and assume a disposable seeded database; the shared-dev test
  row and file were removed after verification.

## Env/secrets added

`OBJECT_STORE_BACKEND`, `OBJECT_STORE_LOCAL_ROOT`, `FILINGS_BUCKET`, `S3_ENDPOINT_URL`,
`AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`,
`ACQUISITION_RATE_PER_SECOND`, `ACQUISITION_MAX_ATTEMPTS`, `MANUAL_UPLOAD_MAX_BYTES`,
`SOURCE_EXCHANGE_XBRL_ENABLED`, `SOURCE_EXCHANGE_ANNOUNCEMENTS_ENABLED`,
`SOURCE_COMPANY_IR_ENABLED`, and the two exchange URL-template variables.

## Verification

- `make verify`: 40 Python passed, 6 opt-in skipped; TS/ESLint and 2 frontend tests passed.
- Live S04 API: 1 passed. Live PostgreSQL integrity: 4 passed. Alembic reports `0003 (head)`.

## Next: S05 — expected entry state

Consume only `filings.status='fetched'`; fetch bytes from `s3_raw`, preserve the filing ID,
and emit parse outputs without mutating acquisition provenance. **Human action now:** counsel
reviews `worker/acquire/SOURCES.md` in parallel with S05–S07; automated flags stay OFF.
