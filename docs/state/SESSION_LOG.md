# Session log

## S01 — 2026-08-14

Status: complete.

- Scaffolded API, worker, frontend, prompts, infrastructure, documentation, and tests.
- Locked Python and frontend dependencies; CI mirrors `make verify` on Python 3.12/Node 20.
- Verified the six-service Compose stack, API dependency health, and served frontend.
- Local verification: 10 Python tests + 1 frontend test passed.
- Browser-plugin visual inspection was unavailable due to the host browser bridge; HTTP,
  component-test, and ECharts build checks passed as the documented fallback.

## S02 — 2026-08-14

Status: complete.

- Added the full PostgreSQL relational spine, Alembic head `0001`, vector embeddings,
  native monthly event partitions, and documented the partitioning decision.
- Enforced extraction version identity and QA-passed public pins in PostgreSQL; metrics
  and scores must reference a pin.
- Added and validated 120 representative BRSR field definitions at schema v0.1.0.
- Seeded 20 companies across six sectors, 40 filings, deliberate gaps/outliers, four
  demo plan users, and one Studio organisation/draft; two consecutive runs were stable.
- Verified 14 offline Python tests, 3 live PostgreSQL integration tests, strict typing,
  linting, TypeScript compilation, and the frontend suite.

## S03 — 2026-08-14

Status: complete.

- Added Argon2 signup/login/email verification and JWT access/refresh rotation with
  family-wide reuse detection and revocation.
- Added database-enforced org context, owner/member invites, platform-admin plan changes,
  composable tier gates, Redis rate limits, and quota scaffolds.
- Made first-party tracking live with registered batched events, anonymous cookies,
  login-time attribution, server-side emits, and privacy export/delete.
- Built signup/login/verify UX, org switching, tier-aware locked navigation, cookie
  disclosure, and the typed pageview/custom-event beacon.
- Verified 24 offline Python tests, 4 live database tests, 1 live S03 API flow, strict
  typing/linting, and 2 frontend tests. Browser bridge initialization was unavailable;
  live persistence plus the component beacon test served as the recorded fallback.

## S04 — 2026-08-14

Status: complete.

- Added governed registry construction with market-cap ranking, CIN validation, and a
  committed NIC-derived sector taxonomy.
- Added default-OFF exchange XBRL, announcement PDF, and company-IR discovery adapters with
  polite rate limits, persisted cursors, SHA-256 dedupe, and bounded Celery retries.
- Added local/S3 raw-object storage at `raw/{cin}/{fy}/{filename}`, acquisition provenance,
  statuses/errors, migration `0003`, and six synthetic offline artifacts.
- Added platform-admin manual upload/API and CLI fallback plus sector × mcap coverage API.
- Committed `worker/acquire/SOURCES.md`; source flags remain OFF pending human legal review.
- Verified 40 offline Python tests, 4 live database tests, 1 live S04 API flow, strict
  typing/linting, TypeScript/ESLint, and 2 frontend tests.

## S05 — 2026-08-14

Status: complete.

- Added XBRL concept/context/unit parsing, tested canonical conversions, and versioned fact
  emission with full source context.
- Added PyMuPDF section location, ambiguity confidence, table-region flags, 150-dpi page
  images, deterministic embeddings, parse statistics, and reparse orchestration.
- Added migration `0004` for pipeline metadata and validated it on Compose PostgreSQL.

## S06 — 2026-08-14

Status: complete.

- Added schema-constrained section extraction, table-image references, retries, spend
  accounting, citation tripwires, Indian-number parsing, and relation checks.
- Added stratified QA sampling, admin queue/UI, human correction versions, family accuracy,
  and QA/confidence/accuracy pin gating.
- Added the offline benchmark harness and fixtures; both committed families achieved 100%.

## S07 — 2026-08-14

Status: complete.

- Added deterministic pinned-field metrics, normalized intensities, percentiles with the
  minimum-sector guard, and YoY deltas.
- Added explainable completeness, substance/boilerplate, and assurance-readiness scores,
  shared-phrase corpus detection, method versioning, nightly/pin-change tasks, and drift API.
- Added single-source scoring configuration and generated public methodology. Two live seeded
  rebuilds produced identical counts: 3,850 metrics and 120 scores.
- Phase 1 complete; 70 offline tests plus 4 live database tests passed.

## S08 — 2026-08-14

Status: complete (offline contracts).

- Added the semantic catalog, validated DSL, parameterised compiler, central tier/cohort policy,
  lineage response envelope, Redis cache invalidation, and governed board PDF.

## S09 — 2026-08-14

Status: complete (browser pass backlogged).

- Added design tokens, styleguide, chart kit with honest states and PNG export, tier-aware shell,
  typed TanStack query layer, URL state, and citation metadata.

## S10 — 2026-08-14

Status: complete (browser pass backlogged).

- Built sector, company, peer, materiality, and assurance surfaces with smart filters, gap-panel
  tracking, learning teasers, and PDF export workflow.

## S11 — 2026-08-14

Status: complete (offline FakeLLM).

- Added catalog-aware NLQ, transparent query chips, inherited semantic enforcement, tier quotas,
  out-of-scope refusal, and shareable views.

## S12 — 2026-08-14

Status: complete (live visual/service checks backlogged).

- Added lineage viewing, correction tickets, company annotations, Learning Library authoring/search,
  methodology coverage/SLA/changelog, citations, and migration `0005`.
- Phase 2 verification: 73 Python passed, 6 skipped; Ruff/mypy/TypeScript/ESLint green; 3 frontend
  test files passed. Migration/seed/materialisation and core API flows passed live on Compose.
  Browser bridge initialization was unavailable, so visual/axe/Lighthouse inspection is backlogged.

## S13 — 2026-08-15

Status: complete.

- Expanded schema `1.0.0` to 300+ data-defined fields covering Section A, the 9×12 Section B
  matrix, all principles, Leadership indicators, repeating groups, relations, and BRSR Core.
- Added the schema linter, typed answer CRUD, single-editor locking, comments, tiered validation,
  per-section/Core progress, prior-year candidates, and the generated Studio questionnaire UI.

## S14 — 2026-08-15

Status: complete.

- Added tenant-isolated PDF/DOCX/XLSX intake, classification, parsed private corpora, evidence
  retrieval, verbatim-quote tripwire, governed proposals, human decisions, token quotas, and
  document-gap guidance. AI proposals never overwrite human answers or count before review.

## S15 — 2026-08-15

Status: complete (domain sign-off required before real-company use).

- Added XBRL instance generation and validation adapter, hard export gates, draft PDF/DOCX with
  provenance and submission note, contextual assurance gap PDF, artifact history and staleness.
- Phase 3 focused checks cover 15-error validation goldens, org isolation, quote tripwire,
  AI-review blocking, XBRL/XML, PDF/DOCX structure, Bioedge agenda, schema coverage and routes.

## S16 — 2026-08-15

Status: complete (visual/keyboard browser pass backlogged).

- Added first-party funnel/feature/sector analytics, deterministic embedding-clustered NLQ themes,
  the weekly team digest, 13-month raw retention and daily aggregates.
- Added governed lead scoring, signal timelines, context-card email, HMAC webhook retries,
  14-day organisation suppression, absolute opt-out and BD outcome quality reporting.
- Added scoped deep-dive requests with the `new → scoped → quoted → delivered` admin workflow,
  contextual expert CTAs, and a user-facing analytics preference surface.
- Migration `0007` applied live; S16 API smoke checks passed. `make verify` passed 94 Python tests
  (6 integration skips), strict Python/TypeScript lint and typing, plus 7 frontend tests.

## S17 — 2026-08-15

Status: complete (pricing/billing browser pass backlogged).

- Added data-defined plans, admin licence assignment with seats and terms, active/grace/read-only
  enforcement, manual invoice requests and a deliberately non-charging Razorpay adapter boundary.
- Unified NLQ/day, Studio token/month, seat and export/month enforcement with 80% headroom notices
  and a registered first-party warning event.
- Added Research-owner scoped API key issue/list/revoke, per-key limits, the public-measure-only
  `/api/v1/query`, and cohort-safe CSV/Parquet aggregate exports with embedded licence metadata.
- Added config-rendered pricing/FAQ and invoice-request UI, board-PDF theming, Studio PDF/DOCX
  typography, and the manual full-corpus fulfilment runbook.
- Migration `0008` applied live; rebuilt API returned all four plans and all five S17 route groups.
  `make verify` passed 115 Python tests (6 integration skips), strict Python/TypeScript checks and
  8 frontend tests.

## S18 — 2026-08-15

Status: complete (visual browser pass backlogged).

- Added the canonical experience contract and an intent-led responsive shell with separate journey
  and utility navigation, active-route semantics, skip navigation, mobile Escape/focus handling,
  and unchanged sign-in/organisation switching.
- Rebuilt home around Explore, Analyse, and File outcomes, a private-by-default analysis promise,
  and a real QA-pinned FY25 sector-completeness insight with honest loading/suppression/error states.
- Added staged `/explore`, `/analyse`, and `/learn` journeys while keeping all legacy/indexable and
  saved-query routes; renamed Assurance trends, Filing Studio, Ask BRSR Lens, Refine this view, and
  Peer benchmarks without changing stable API or route contracts.
- Registered four entry events constrained to intent/auth/tier/surface metadata and added shell,
  route, keyboard, copy, query-state, and event-privacy tests.
- `make verify` passed schema validation, Ruff, strict mypy, 115 Python tests (6 integration skips),
  TypeScript/ESLint, and 18 frontend tests. The browser bridge exposed no browser instance.

## S19 — 2026-08-15

Status: complete (visual browser pass backlogged).

- Added a versioned eight-question registry spanning sector completeness, substance, BRSR Core
  readiness, materiality evidence, assurance context, market-cap quality, emissions, and boilerplate.
- Replaced `/explore` with a tier-aware guided hub containing governed results, human-readable
  cohorts, takeaways, explanations, robust states, shareable query state, and one-action expert paths.
- Added reusable contextual follow-ups and `/api/nlq` `base_dsl` merge provenance. Same-dimension
  follow-up filters override base context; other filters inherit before central validation/policy.
- Reframed Ask transparency copy and removed raw free-text questions from first-party analytics.
  Registered four privacy-safe S19 events and added merge, policy, route, tier, URL, and payload tests.
- `make verify` passed schema validation, Ruff, strict mypy, 117 Python tests (6 integration skips),
  TypeScript/ESLint, and 22 frontend tests. The browser runtime exposed no browser instance; live
  HTTP, responsive CSS, component interaction, keyboard-native control, and production-build checks
  passed as the fallback.

## NSE BRSR ingestion — 2026-08-16

Status: complete.

- Added official NIFTY 50 registry and NSE BRSR portal discovery, revision selection, polite
  fail-closed retrieval, checksum-based raw storage, and lossless XBRL fact persistence.
- Removed the legacy fictional corpus and changed `make seed` to create access/taxonomy records
  only. Added migration `0009`, ingestion run/state audit tables, and filing source dates.
- Added deterministic `initial`, cursor-based `next`, and refresh CLI modes; configurable scheduled
  refresh; and an admin source/run/company/FY/sector inventory dashboard.
- Live FY 2024–25 import completed 25/25 companies with zero missing/errors and 55,105 raw facts.
- Verification: Ruff and strict mypy passed; 122 Python tests passed (6 skipped); TypeScript,
  ESLint, and 22 frontend tests passed.

## Provisional NSE Explorer publication — 2026-08-16

Status: complete in source/database; one Docker image refresh remains environment-blocked.

- Added migration `0010`, a versioned 16-row NSE concept mapping registry, explicit assumptions,
  confidence and an Admin accept/needs-review/reject workflow with reviewer notes and timestamps.
- Converted MJ/GJ/TJ to GJ, kL to kL, and emissions to tCO2e; documented the provisional `MtCO2e`
  interpretation. Added NIFTY-cohort turnover scale inference for absolute INR normalization.
- Published 400 provisional extracted fields/pins and materialized 425 metrics plus 75 scores for
  25 FY25 companies. Live API checks returned 25 rows with lineage for energy, water, Scope 1 and
  all three per-INR-crore intensities.
- Added Scope 1+2 totals, five real-data guided Explorer questions, an on-screen provisional notice,
  `--publish` ingestion mode and automatic scheduled rematerialization.
- Verification: 124 Python tests passed (6 skipped); Ruff, strict mypy, TypeScript and ESLint passed;
  22 frontend tests passed. Admin review update/restore passed live. No browser instance was
  available. Docker rebuild approval was blocked by the environment usage limit.

## Pre-production review and remediation — 2026-08-16

Status: complete. `make verify` green; all findings actioned in the same pass.

- Found `make verify` red, not green as the previous handoff recorded: a prior run had masked the
  exit code behind a pipe. `test_production_rejects_default_jwt_secret` was reading the developer's
  `.env`, so the production guard passed without ever being exercised. Pinned to `_env_file=None`.
- Replaced the magnitude-based turnover scale heuristic, which published Coal India ten times low
  (reported `143368.92` is INR crore, about INR 1.43 lakh crore) and ranked it second-worst on
  energy intensity at 1,331.68. Dr. Reddy's `231154` falls in the same numeric band but is
  genuinely INR million, so no threshold could separate the two. Scale now comes from a reviewed
  per-issuer registry in `taxonomy/nse_concept_mappings.yaml`; unregistered issuers below the
  absolute threshold are withheld rather than guessed. Coal India now publishes INR 1,43,369 crore
  and an energy intensity of 133.17.
- Established that the XBRL `decimals` attribute cannot recover reporting scale (Coal India
  `decimals="2"` crore, Dr. Reddy's `decimals="0"` million, Infosys `decimals="2"` absolute). It is
  now retained on `xbrl_facts.decimals` for provenance and explicitly excluded from scale
  inference.
- Extended production settings validation to reject `AUTH_EXPOSE_VERIFICATION_TOKEN=true` and
  `LLM_PROVIDER=fake` when `APP_ENV=production`. The former returned verification and org-invite
  tokens in API responses.
- Added identity-based plausibility screens (energy parts sum to total, water sources sum to
  withdrawal, non-negativity) that withhold a failing metric and everything derived from it.
  Deliberately no emissions-per-energy band, since Scope 1 legitimately includes non-energy
  fugitive and process emissions. All 25 FY25 filings pass.
- Added `metrics.contributing_pin_ids` so additive and multi-numerator metrics carry every
  contributing pin instead of anchoring lineage to the first component.
- Fixed dev/prod parity in compose: parameterized mailhog host ports, mounted `taxonomy/`,
  `scoring.yaml`, `plans.yaml` and `./worker` so api and worker stop running stale baked config.
  The live catalog had been serving `1.0.0` with none of the session's new measures.
- Created the three mandatory launch gate files under `docs/gates/`, all explicitly unsigned.
- Lowered the cohort suppression minimum from 8 to 5 on request. Financial Services (n=6) now
  receives sector percentiles; all other sectors remain below five.
- Verification: Ruff, strict mypy, 134 Python tests (6 skipped), TypeScript, ESLint and 22 frontend
  tests passed. Migration `0011` applied and the FY25 cohort republished and rematerialized live.
