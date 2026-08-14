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
