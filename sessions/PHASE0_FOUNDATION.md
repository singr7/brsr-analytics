# PHASE 0 — Foundation (S01–S03)

---
## S01 — Scaffold, dev environment, CI
**GOAL:** Cloneable repo; `make up && make verify && make seed` green on a clean machine; wired FastAPI/Celery/React skeletons.

**READ:** 00_ARCHITECTURE §1–2, 01_CONVENTIONS (full), QA_PLAN §1–2.

**TASKS**
1. Layout per conventions §1; Python 3.12 (uv lockfiles), Node 20 + pnpm.
2. Compose: `postgres` (pgvector/pgvector:pg16 image, healthcheck), `redis:7`, `api` (reload), `worker`, `frontend` (vite), `mailhog` (SES stand-in for lead emails from day one).
3. FastAPI skeleton: config (pydantic-settings), `/healthz` (DB, Redis, LLM-config-present check — not a live call), JSON logging, request-ID middleware.
4. `services/llm.py` v0: provider-agnostic interface (`complete(prompt_key, version, variables, schema) -> parsed`), real client + **FakeLLM** loading `prompts/fixtures/{prompt_key}@{version}/{case}.json`; env-selected. One demo prompt YAML + fixture to prove the loop.
5. `services/track.py` v0 + `events.yaml` registry + `events` table can wait for S02 — for now an in-memory sink with the registry test wired.
6. React skeleton: Vite TS, Tailwind, ECharts installed with one demo chart page, health status footer.
7. Makefile all verbs (stubs exit 0 with "not yet: SNN"); ruff/mypy/tsc/eslint/pytest configs; CI workflow: compose (pg+redis) → `make verify`, dep caching.
8. `.env.example` complete; `docs/state/` seeded.

**SELF-CHECK:** clean-clone sim green · FakeLLM round-trip test passes with no network · demo ECharts renders · CI green.
**COMMITS:** `chore(scaffold) [S01]`, `infra(dev): compose [S01]`, `feat(core): llm client + fake [S01]`, close.
**HANDOFF:** service names/ports, llm interface signature, prompt/fixture file pattern, config var list.

---
## S02 — Domain schema, migrations, seed
**GOAL:** The full relational spine from 00_ARCHITECTURE §3, with versioned extraction and lineage columns that everything downstream leans on.

**READ:** HANDOFF, 00_ARCHITECTURE §3, `core/config.py`.

**TASKS**
1. Models + initial migration: `companies, filings, filing_pages, field_defs, extracted_fields (versioned, confidence, method, source_page, source_span, qa_status)`, `metrics, scores`, `users/orgs/memberships/plans/api_keys`, `events (monthly partitions via pg_partman-style manual DDL — document choice)`, `leads, deepdive_requests`, `studio_orgs/studio_filings/studio_answers/studio_docs`.
2. Constraints that encode doctrine: unique `(filing_id, field_key, version)`; check `qa_status='sampled_ok' OR confidence IS NOT NULL`; `metrics/scores` FK to a `field_version_pin` snapshot table (how public views pin QA-passed versions — design this small table carefully; it is the published-number rule's enforcement point).
3. `field_defs` loader: `taxonomy/form_schema.yaml` v0 — encode a representative subset now (~120 fields: Section A basics, P6 environment Core KPIs incl. energy/emissions/water/waste, P3 workforce, P5 human-rights counts, assurance block) with dtype/unit/principle/xbrl_concept placeholders; loader upserts by `field_key` with schema-version stamp. (Full ~2,000-field encode is S13's job with the real taxonomy; the subset unblocks the whole pipeline now.)
4. pgvector: `embeddings(owner_kind filing_page|field_def|library_note, owner_id, embedding vector(1024), model)` + ivfflat index.
5. `make seed`: 20 fixture companies across 6 sectors/3 mcap bands, 2 FYs of synthetic `extracted_fields` (generator with sector-plausible values + deliberate gaps/outliers documented in the generator), demo users per tier, one studio org.
6. Property tests: version-pin behavior (new unreviewed version does NOT change pinned public value), partition insert routing.

**SELF-CHECK:** migrations clean on empty DB · seed idempotent · pin test green · field_defs loader re-runnable · verify green.
**COMMITS:** `feat(db): spine + versioned extraction + pins [S02]`, `feat(schema): form_schema v0 + loader [S02]`, `feat(seed) [S02]`, close.
**HANDOFF:** table list w/ key columns, pin-table semantics (exact), field_key naming grammar (`p6.e1.energy_total_gj` style — write it down), seed inventory.

---
## S03 — Auth, org model, access tiers, first-party tracking live
**GOAL:** Public-anonymous + registered + tiered access working end-to-end; the analytics beacon capturing events into Postgres.

**READ:** HANDOFF, `models/users*.py`, `services/track.py` v0, QA_PLAN §5 (auth cases).

**TASKS**
1. Auth: argon2 + JWT access/refresh (rotation, reuse detection); signup (email verify via mailhog), login, `/me`; org create/invite (roles owner|member).
2. Tier gates: dependency `require_plan(*tiers)`; anonymous allowed on public routes with `anon_id` cookie (first-party, httpOnly=false by design for the beacon — document); plan changes admin-only endpoint (billing-lite comes S17).
3. Tracking live: `events` writes via `track.py` (batched inserts), JS beacon (`frontend/src/lib/track.ts`: pageviews, registered custom events, anon→user merge on login — merge job stitches `anon_id` history), server-side emits for API-driven events. `events.yaml` seeded with the Phase-2/3 names already (viewed_company, viewed_gap_panel, nlq_asked, export_generated, studio_gap_report, pricing_viewed, deepdive_requested…).
4. Rate limits: Redis-backed per-IP (public API) + per-org (authed); NLQ/LLM quotas scaffolded (enforced later).
5. Frontend: signup/login/verify pages, org switcher, tier-aware nav (locked items visible with upgrade affordance — conversion surface, clearly labeled).
6. Privacy plumbing: `/api/privacy/export` + `/delete` for a user's events (cheap now, painful later), cookie disclosure component.

**SELF-CHECK:** auth suite (happy/expired/refresh-reuse/role/tier denials) · cross-org isolation test · anon→user merge test · beacon events visible in table from a Playwright pageview · verify green.
**COMMITS:** `feat(auth): jwt + orgs + tiers [S03]`, `feat(track): beacon + merge + registry [S03]`, close.
**HANDOFF:** route-protection dependency names, tier matrix, event names live, beacon usage, merge semantics. Next: S04 (PHASE1).
