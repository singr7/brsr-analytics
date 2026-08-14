# PHASE 1 — Data Pipeline (S04–S07)
*The corpus sessions. Doctrine: every value carries (source, page, span, confidence, version); nothing reaches public views except via QA-pinned materialisations.*

---
## S04 — Filing acquisition & company registry
**GOAL:** A governed pipeline that fills S3 with raw filings (XBRL + PDF) for the target 1,000 companies, with statuses, retries, and a manual-upload fallback — legally reviewable by design.

**READ:** HANDOFF, 00_ARCHITECTURE §3 (filings), DEPLOYMENT §5 (legal gate note).

**TASKS**
1. Registry: `ops/registry/build_registry.py` — assemble the top-1,000 list (index constituents by mcap) into `companies` with CIN/ticker/sector mapping; sector taxonomy file (`taxonomy/sectors.yaml`, NIC-based groups) committed and documented.
2. Fetchers (`worker/acquire/`): pluggable source adapters — exchange XBRL/announcement endpoints and company-IR page adapter — each with: polite rate limiting (config), robots/ToS notes in adapter docstring, checksum dedupe, resume-safe cursors. **A `SOURCES.md` documents every source, its terms status, and a per-source enable flag defaulting OFF until the human legal gate flips it.** (The agent builds capability; the human authorises use — this is the legal gate's mechanism.)
3. Manual/bulk upload path: admin endpoint + CLI to attach a filing PDF/XBRL to (company, FY) — the guaranteed-lawful fallback that also serves pilot partners sending their own files.
4. Acquisition job orchestration: per-company-FY task → download → S3 `raw/{cin}/{fy}/…` → `filings` row (status fetched|missing|error, source recorded) → coverage dashboard query (`GET /admin/coverage`: % by sector/mcap band — the operator's daily view during corpus build).
5. Fixtures: 6 synthetic "downloaded" artifacts (2 XBRL, 4 PDF — small, constructed; see QA_PLAN §3) wired through the pipeline in tests; live fetch is `@live`-marked only.

**SELF-CHECK:** adapter contract tests (rate-limit honored via fake clock, dedupe, resume) · manual upload → filing row + S3 object · coverage query correct on fixtures · all adapters default-disabled · verify green.
**COMMITS:** `feat(acquire): registry + adapters (default off) + manual path [S04]`, `feat(admin): coverage [S04]`, close.
**HANDOFF:** adapter interface, SOURCES.md status table, S3 layout, coverage endpoint. **Flag to human: legal review of SOURCES.md starts now, parallel to S05–S07.**

---
## S05 — Parsing: XBRL first-class, PDF segmentation
**GOAL:** Raw artifacts → structured candidates: XBRL facts mapped to `field_defs`; PDFs segmented to BRSR sections with page text + images ready for LLM extraction.

**READ:** HANDOFF, `taxonomy/form_schema.yaml`, `models/filings*.py`.

**TASKS**
1. XBRL path (`worker/parse/xbrl.py`): read instance docs (arelle-assisted), map concepts → `field_key` via the mapping column in field_defs; emit `extracted_fields` rows `method='xbrl', confidence=1.0` (context/unit handling: periods, decimals, unit families normalised via `services/units.py` — GJ/kWh/MWh, KL/ML, tCO2e — conversion table tested against hand values).
2. PDF path (`worker/parse/pdf.py`): pymupdf text + layout; **BRSR section locator** — find the BRSR block inside a large annual report (regex/heading heuristics + fuzzy anchors for "SECTION A", principle headings; scored candidates, human-visible when ambiguous); store `filing_pages` (text + rendered page PNG to S3 at 150 dpi for vision fallback + the lineage viewer).
3. Table candidate detection: pymupdf word-box clustering → table regions flagged per page (metadata for S06's prompts; do not attempt full table structure recovery in code — LLM+vision does that better).
4. Embeddings job: filing_pages → pgvector (batched, model from config) for later NLQ/citation retrieval.
5. Idempotency: reparse (filing) wipes+rewrites its candidates at a new parse_version; parsed stats on filing row (pages, sections found, xbrl fact count).

**SELF-CHECK:** XBRL fixture → exact expected field rows (golden) · unit conversions vs hand values · section locator finds the BRSR block in all 4 PDF fixtures incl. the deliberately messy one (starts mid-page, renamed headings) and reports ambiguity on the trap fixture · reparse idempotent · verify green.
**COMMITS:** `feat(parse): xbrl → fields + units [S05]`, `feat(parse): pdf sectioning + pages + embeddings [S05]`, close.
**HANDOFF:** parse outputs schema, section-locator confidence semantics, page-image S3 pattern, unit table location.

---
## S06 — LLM extraction engine + QA workflow
**GOAL:** The hard one: PDF-only fields extracted at benchmark-grade accuracy with confidence, citations, and a human QA loop — fully offline-testable.

**READ:** HANDOFF, `services/llm.py`, prompts pattern, field_key grammar, QA_PLAN §4 (benchmark protocol).

**TASKS**
1. Prompt suite (`prompts/extract_*.yaml`): per section/principle prompts taking (field subset defs + page text [+ page image for table-flagged pages]) → JSON-schema output `{field_key, value, unit, source_page, source_quote, confidence, not_found?}`. Schema-constrained decoding; **`source_quote` must appear verbatim on the cited page** (post-validation check — a hallucination tripwire that zeroes confidence and flags).
2. Extraction orchestrator (`worker/extract/run.py`): plan per filing = fields missing after XBRL → batch by section → LLM calls with retry/quota → `extracted_fields (method='llm')` versioned; token/cost accounting per filing to `llm_usage` (the spend meter).
3. Numeric hygiene: value parsing (Indian digit grouping, lakh/crore, %, ranges, "Nil"), declared-relation cross-checks (totals vs breakdowns) — failures downgrade confidence + flag.
4. **QA workflow:** stratified sampling job (field family × confidence band) → review queue API + minimal admin UI (page image + quote highlight + accept/correct); corrections create human-method versions and feed the benchmark set; per-family accuracy stats (`GET /admin/quality`).
5. Benchmark harness: `make bench-extraction` — prompt suite via FakeLLM fixtures against the golden set, accuracy by family; `@live` nightly variant.
6. Publish gating: `field_version_pin` updater honors policy (`publish_threshold` confidence, family accuracy ≥ target, qa_status) — the mechanism the editorial gate signs.

**SELF-CHECK:** fixture extraction reproduces goldens ≥ target · fabricated-quote fixture → flagged (tripwire test) · relation cross-check test · QA correction round-trip updates pin only after policy passes · cost accounting sums · verify green, zero live calls.
**COMMITS:** `feat(extract): prompts + orchestrator + tripwires [S06]`, `feat(qa): sampling + review + quality stats [S06]`, `feat(policy): publish gating [S06]`, close.
**HANDOFF:** prompt_keys@versions, extraction contract, QA endpoints, policy knobs, benchmark how-to + fixture accuracy achieved.

---
## S07 — Normalisation, scoring engines, materialisation
**GOAL:** From QA-pinned fields to the analytics that make the portal citable: metrics star-schema, percentiles/YoY, the two signature scores.

**READ:** HANDOFF, `metrics/scores` models, pin semantics (S02 note).

**TASKS**
1. `worker/score/metrics.py`: materialise `metrics` from pinned fields — normalised KPIs (intensities via declared denominators), sector/all percentiles (**min-n guard: suppress where sector n < 8** — small-cohort honesty), YoY deltas. `make rebuild-metrics` = full deterministic rebuild (test: rebuild twice → identical).
2. **Completeness score:** weighted coverage of Core + Essential fields (weights in `scoring.yaml` with rationale comments); components stored for explainability.
3. **Substance-vs-boilerplate index (the signature):** per narrative field family: quantified-target presence (regex + LLM verdict prompt w/ fixtures), dated commitments, named methodologies, and **cross-corpus template detection** (phrases near-verbatim in >k companies score as boilerplate — shared-phrase table computed from the corpus itself); combined per `scoring.yaml`; **methodology writeup auto-generated into `docs/methodology/substance_index.md` from the same config** (single source of truth for the public methodology page).
4. **Assurance-readiness score** (feeds Bioedge conversations): assurance status + Core coverage + lineage quality → components.
5. Orchestration: nightly + on-pin-change; scores versioned by method_version; `GET /admin/score-drift` between method versions (protects against silent methodology shifts).
6. Golden analytics tests: seed corpus → exact expected percentiles/scores (hand-computed for 3 companies, committed with working shown).

**SELF-CHECK:** rebuild determinism · min-n suppression · boilerplate detector flags the seeded template-twin companies · hand-computed goldens match · methodology doc regenerates from config · verify green.
**COMMITS:** `feat(score): metrics + percentiles + yoy [S07]`, `feat(score): substance + completeness + assurance-readiness [S07]`, `feat(admin): drift report [S07]`, close.
**HANDOFF:** metric/score key catalog (the semantic layer's raw material), scoring.yaml knobs, methodology doc path. **Flag to human: editorial-gate criteria now testable — review `/admin/quality` + policy before any public exposure (S19 signs).** Next: S08 (PHASE2).
