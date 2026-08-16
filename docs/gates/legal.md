# Legal gate — UNSIGNED

Per DEPLOYMENT.md §5, counsel reviews the items below and records a dated sign-off here.
Flipping an acquisition source flag on in production configuration is the technical expression
of that signature. **All automated-source flags remain `false` until this file is signed.**

## What counsel is asked to review

- `worker/acquire/SOURCES.md` — each acquisition source, its terms basis and access pattern.
- The official NSE BRSR portal integration specifically: `docs/operations/NSE_BRSR_INGESTION.md`
  covers source policy, the declared contact address and the request rate.
- The public methodology and correction-SLA pages.
- The private-analysis privacy and retention promise.
- The Studio liability line.

## Current source flag state

All default to `false` in `.env.example` and in `api/app/core/config.py`:

- `SOURCE_EXCHANGE_XBRL_ENABLED`
- `SOURCE_EXCHANGE_ANNOUNCEMENTS_ENABLED`
- `SOURCE_COMPANY_IR_ENABLED`
- `SOURCE_NSE_BRSR_ENABLED`

`NSE_BRSR_CONTACT` still carries the placeholder `legal-contact@brsrlens.local` and must be set
to a real monitored address before the NSE source is enabled.

## Sign-off

| Field | Value |
|---|---|
| Reviewer | _unsigned_ |
| Date | _unsigned_ |
| Sources approved | _none_ |
| Conditions / limits | _unsigned_ |
