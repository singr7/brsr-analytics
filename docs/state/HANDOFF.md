# HANDOFF — after S03 (2026-08-14)

## Repo state: `main` · dev services up · migrations head `0002`

## Delivered

- Argon2 password hashing and signed JWT access/refresh pairs. Refresh tokens rotate under
  a family ID; reuse revokes the whole family and records `reuse_detected=true`.
- Signup, Mailhog email verification, login, refresh, `/me`, organisation create/invite/
  accept, platform-admin-only plan changes, and membership-backed org isolation.
- First-party event ingestion into PostgreSQL partitions with registry validation, batch
  inserts, anonymous IDs, login-time anon→user stitching, and server-side auth/org emits.
- Redis per-IP and per-org rate-limit primitives. Plan records now carry NLQ and LLM-token
  quota scaffolds for later enforcement.
- Authenticated event export/delete privacy endpoints and a disclosed, one-year first-party
  `anon_id` cookie. It is `httpOnly=false` deliberately so the browser beacon can use it;
  `SameSite=Lax`, and production adds `Secure`.
- Signup/login/verification UI, org switcher, tier-aware locked navigation with explicit
  upgrade affordances, cookie disclosure, and the typed browser beacon.

## Auth and access contracts

- Dependencies: `optional_user`, `current_user` / `CurrentUser`, `current_org` /
  `CurrentOrg`, `require_role(*roles)`, `require_plan(*tiers)` in `core/access.py`.
- Auth routes: `POST /api/auth/signup|verify|login|refresh`, `GET /api/auth/me`.
- Org routes: `POST /api/orgs`, `/api/orgs/invites`, `/api/orgs/invites/accept`.
  Org-scoped calls pass `X-Org-ID`; membership is always checked in the database.
- Plan route: `PATCH /api/admin/orgs/{org_id}/plan`; only `users.is_admin=true`.
  The seeded research user is the local platform admin.
- Privacy: `GET /api/privacy/export`, `DELETE /api/privacy/delete`.
- Tier doctrine: `explore|pro|studio|research`; feature routes compose
  `require_plan(...)`. Locked items remain visible in the frontend.

## Tracking contracts

- Beacon: `track(name, properties)` and `trackPageview()` in `frontend/src/lib/track.ts`.
  Requests include credentials and an access token when present; the server accepts at most
  50 registered events per batch.
- Live registry: `demo_chart_viewed`, `page_viewed`, `signup_completed`,
  `login_completed`, `org_created`, `viewed_company`, `viewed_gap_panel`, `nlq_asked`,
  `export_generated`, `studio_gap_report`, `pricing_viewed`, `deepdive_requested`.
- Merge semantics: login updates only rows matching the browser's `anon_id` whose
  `user_id IS NULL`; already-attributed history is never reassigned.

## Verification

- `make verify`: 25 Python tests passed, 5 opt-in integration tests skipped; TypeScript,
  ESLint, and 2 frontend tests passed.
- Live PostgreSQL suite: 4 passed, including partition routing, pin integrity, cross-org
  isolation, and anonymous-history merge.
- Live S03 API suite: passed refresh reuse, isolation, beacon persistence, privacy, and
  admin-plan behavior.
- Migration `0002` applied; an empty-database `0001→0002` chain passed and its temporary
  database was removed; the seed ran twice without changing inventory.
- In-app browser initialization was unavailable. The real API persistence test and browser
  component beacon test are the recorded fallback; visual browser QA remains a manual check.

## Demo credentials

- `demo+{explore|pro|studio|research}@brsrlens.local`
- Password: `DemoPassword123!`
- Demo Studio org: `demo-studio`; Studio user is owner. Research user is platform admin.

## Env/secrets added

`JWT_SECRET`, `JWT_ISSUER`, token lifetimes, SMTP host/port/from, `FRONTEND_URL`,
`AUTH_EXPOSE_VERIFICATION_TOKEN`, and public/org rate limits. Production startup rejects a
default or sub-32-character JWT secret. Set token exposure to `false` outside local dev.

## Next: S04 — expected entry state

Build acquisition on the authenticated service spine. Public acquisition/status routes may
use the per-IP limiter; operator/org routes must use `CurrentOrg` plus the appropriate role
and plan gate. Emit only names already registered in `events.yaml`.
