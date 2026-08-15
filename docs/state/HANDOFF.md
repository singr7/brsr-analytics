# HANDOFF — after S12 / Phase 2 (2026-08-14)

## Phase 2 delivery

- `taxonomy/semantic.yaml` is the versioned semantic catalog. The public DSL is
  `{measures[], dimensions[], filters[], shape, sort?, limit?}` with five governed shapes.
- `POST /api/query` compiles only governed materialisations with bound parameters. Redis cache
  identity is `(canonical DSL hash, tier)` and scoring rebuilds invalidate it. Explore receives
  aggregates; paid tiers can request company detail. Cohorts below eight are suppressed and lower
  performer rankings are anonymised centrally.
- Responses contain data, cell lineage refs, applied policy, catalog version, and cache status.
  `POST /api/exports/peer-board` produces a governed Pro-tier PDF.
- `POST /api/nlq` injects the catalog, validates returned DSL, inherits semantic policy, applies
  tier quotas, and refuses investment/out-of-corpus questions. The UI exposes interpretation and
  editable query chips.
- Public routes are `/`, `/sectors`, `/materiality`, `/assurance`, `/methodology`, `/library`, and
  `/pricing`; paid workflows are `/companies` and `/benchmarks`. `/ask` is transparent NLQ and
  `/styleguide` documents tokens and chart states. Query state is URL parameter `q` with JSON DSL.
- Trust APIs cover lineage, corrections, company annotations, library search/authoring, and public
  methodology. Migration `0005` adds their durable models. ADR 0002 records static rendering.

## Verification after Phase 2

- 73 Python tests passed, 6 opt-in live-service tests skipped; strict Ruff and mypy passed.
- TypeScript compilation and ESLint passed; 3 Vitest files passed.
- Injection, tier policy, cache identity, and shareable URL contracts have deterministic tests.
- Live Compose migration, seed, materialisation, query/cache, NLQ, library, methodology, Pro
  company-lineage, and board-PDF checks passed. The in-app browser host bridge could not initialize,
  so only the visual/axe/Lighthouse pass remains recorded in BACKLOG.

## Repo state: `main` · dev services up · migrations head `0005`

## Delivered

- S05 parses fetched XBRL with concept/context/unit/decimal lineage and normalises energy,
  water, emissions, mass, percentage, count, and currency units. PDF parsing uses PyMuPDF,
  fuzzy BRSR section anchors, visible ambiguity/confidence, aligned-box table flags, 150-dpi
  page PNGs at `pages/{filing_id}/v{parse_version}/{page}.png`, and configurable embeddings.
- Reparsing increments `filings.parse_version`, replaces current pages/embeddings, preserves
  versioned extracted facts, and updates page/section/XBRL statistics on the filing.
- S06 batches XBRL-missing fields by section through `extract_section@v1`, supplies table-page
  image references, validates schema output, forces non-verbatim citations to zero confidence,
  normalises Indian number formats, checks declared relations, and records token/cost usage.
- Stratified QA sampling, queue/review APIs and the admin review panel support accept/correct.
  Corrections create human versions; `/api/admin/quality` reports family accuracy. Pins move
  only when QA status, confidence, and family-accuracy policy all pass.
- `make bench-extraction` is fully offline and currently reports 100% for both committed
  environmental fixture families. Live LLM access remains disabled by default.
- S07 deterministically materialises pinned numeric fields plus declared-denominator
  intensities, all-company/sector percentiles, YoY deltas, and completeness, substance, and
  assurance-readiness scores. Sector percentiles are suppressed for cohorts smaller than 8.
- Cross-corpus shared phrases drive boilerplate penalties. `scoring.yaml` is the sole method
  configuration; `docs/methodology/substance_index.md` is generated from it. Scores retain
  method versions/config hashes; `/api/admin/score-drift` compares method versions.
- Nightly rebuilds run through the Compose `scheduler`; pin changes enqueue immediate rebuilds.
  Two consecutive seeded-corpus rebuilds
  each produced 3,850 metrics and 120 scores without drift or uniqueness failures.

## Contracts Phase 2 relies on

- Public and semantic-layer routes must read only `metrics` and `scores`; raw
  `extracted_fields` remain an admin/lineage concern. Every materialised row retains a
  `field_version_pin_id` provenance anchor.
- Metric keys are field keys for direct numeric metrics plus
  `normalized.energy_gj_per_inr_crore`, `normalized.water_kl_per_inr_crore`, and
  `normalized.scope12_tco2e_per_inr_crore`.
- Score keys are `completeness`, `substance`, and `assurance_readiness`; component JSON is the
  public explanation source. Current method version is `1.0.0`.
- QA APIs: `POST /api/admin/reviews/sample`, `GET /api/admin/reviews`,
  `PATCH /api/admin/reviews/{id}`, and `GET /api/admin/quality`. Scoring audit API:
  `GET /api/admin/score-drift?from_version=...&to_version=...`.
- Worker entry points: `worker.parse.filing`, `worker.extract.filing`,
  `worker.score.pin_changed`, and `worker.score.rebuild`. Operator commands:
  `make fetch-testdata`, `make bench-extraction`, and `make rebuild-metrics`.

## Sharp edges and human gates

- Source adapters remain default-OFF. Counsel must approve each row in
  `worker/acquire/SOURCES.md` before enabling its flag.
- The editorial gate is mechanically testable but not signed: a human must review
  `/api/admin/quality`, the benchmark corpus, policy thresholds, and the generated methodology
  before public company-level figures are exposed.
- The committed extraction benchmark is deliberately small and synthetic at this stage. Grow
  it toward QA_PLAN's 400 values / 25 real filings through reviewed, lawfully obtained filings.
- The hash embedding model is the deterministic local default. Production can change
  `EMBEDDING_MODEL`, but a provider implementation and model-version re-embed are required.
- Score rebuilds preserve prior method-version scores for drift reports but replace the current
  metric star table. Change `method_version` whenever scoring semantics change.

## Verification

- `make verify`: 70 Python passed, 6 opt-in skipped; strict Ruff/mypy; TypeScript/ESLint;
  2 frontend tests passed.
- `make bench-extraction`: p6.e1 100%, p6.e2 100%; zero live calls.
- PyMuPDF render test confirmed BRSR section extraction and 150-dpi PNG dimensions.
- Compose images rebuilt with PyMuPDF and `scoring.yaml`; Alembic reports `0004 (head)`.
- Live PostgreSQL integrity suite: 4 passed. Seeded materialisation rebuilt twice: 3,850
  metrics and 120 versioned scores each run.

## Prior Phase 1 entry contract (retained for audit)

Phase 2 preserved this contract: semantic and dashboard queries use only pinned materialisations;
raw candidates are exposed only through the dedicated lineage and correction workflow.
