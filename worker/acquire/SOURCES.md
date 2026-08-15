# Acquisition source register

All automated adapters are disabled by default. A production operator may set an enable
flag to `true` only after counsel records approval in the dated legal-gate note. URLs,
credentials, or access obtained for one source must not be reused for another.

| Adapter | Intended material | Terms/robots status | Enable flag | Default |
|---|---|---|---|---|
| `exchange_xbrl` | Exchange-hosted BRSR XBRL | Legal review pending; confirm endpoint terms, redistribution, robots, and contact/rate policy | `SOURCE_EXCHANGE_XBRL_ENABLED` | OFF |
| `exchange_announcements` | Exchange announcement PDFs | Legal review pending; confirm bulk-download and redistribution rights | `SOURCE_EXCHANGE_ANNOUNCEMENTS_ENABLED` | OFF |
| `company_ir` | Filing PDF discovered on a company IR page | Per-domain robots and terms review required; registry supplies the reviewed IR page URL | `SOURCE_COMPANY_IR_ENABLED` | OFF |
| `manual_upload` | Partner/operator-provided PDF or XBRL | Lawful fallback; uploader attests authority under operating procedure | always available to platform admins | ON |

## Operating controls

- Automated clients identify themselves, follow redirects, use the configured global
  `ACQUISITION_RATE_PER_SECOND`, persist a cursor/ETag per source-company-FY, and retry only
  through the acquisition job policy.
- A SHA-256 match for a company-FY reuses the existing object reference. Raw object keys are
  `raw/{cin}/{fy}/{filename}` in `FILINGS_BUCKET`; the S3 backend requests SSE-S3.
- The registry importer accepts an operator-provided, licensed constituent export. It never
  scrapes or downloads index membership. Keep provenance and licence evidence with each run.
- Disabling a source stops new requests; it does not delete already acquired evidence.

## Legal review record

Counsel should record source-by-source decision, review date, reviewer, permitted purpose,
rate/attribution requirements, retention/redistribution conditions, and next-review date in
`docs/gates/legal.md`. S25 requires that signed record before launch.
