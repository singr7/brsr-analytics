# BRSR Lens — Build Plan
### Production-grade BRSR analytics platform + Filing Studio + engagement engine



## What gets built (three pillars, one platform)
1. **Insights** — interactive analytics over ~1,000 companies' BRSR filings: sector scorecards, substance-vs-boilerplate index, materiality maps, assurance tracker, company deep-dives, peer benchmarking — with **natural-language querying**, smart filters, and click-any-number-to-see-the-filing-text lineage.
2. **Filing Studio** — a guided preparation tool: a company uploads its documents (policies, HR data, energy/water records, prior filings) and the system drafts its BRSR in the prescribed format — section-by-section questionnaire, LLM-assisted field mapping with confidence + human review, validations, and exports (SEBI-format XBRL + board-ready PDF/Word draft + assurance-readiness gap report).
3. **Engagement engine** — first-party product analytics, lead scoring, and conversion paths: every high-intent behavior (peer-gap views, gap reports, NLQ patterns, deep-dive requests) routes to Panacea Bioedge with context; on-demand expert deep-dives are a productised request flow.

## Pack contents
| File | Purpose |
|---|---|
| `README.md` | This file — operating manual |
| `00_ARCHITECTURE.md` | Stack decisions (independent), data model spine, LLM usage doctrine, AWS balanced managed/self-managed |
| `01_CONVENTIONS.md` | Repo layout, standards, session protocol + handoff schema (read every session) |
| `sessions/PHASE0_FOUNDATION.md` | S01–S03 scaffold · schema · auth & access tiers |
| `sessions/PHASE1_PIPELINE.md` | S04–S07 filing acquisition · XBRL/PDF parsing · LLM extraction+QA · scoring engines |
| `sessions/PHASE2_INSIGHTS.md` | S08–S12 semantic layer · design system · dashboards · NLQ+smart filters · lineage & library |
| `sessions/PHASE3_FILING_STUDIO.md` | S13–S15 questionnaire engine · doc-to-draft AI · exports (XBRL/PDF/gap report) |
| `UX-revamp.md` | Critical UX evaluation, target journeys, terminology, and acceptance criteria |
| `sessions/PHASE4_ENGAGE_PROD.md` | S16–S17 analytics+lead engine · tiering and billing-lite |
| `sessions/PHASE5_UX_REVAMP.md` | S18–S23 intent-led shell · guided Explore · private BRSR analysis · learning mode · Studio alignment |
| `sessions/PHASE6_PRODUCTION.md` | S24–S25 AWS infra+deploy · corpus · hardening and launch |
| `DEPLOYMENT.md` | Topology, release flow, backups, launch checklist |
| `QA_PLAN.md` | Test strategy incl. extraction-accuracy benchmarks and editorial gates |



## Local development

Session S01 provides the first runnable stack. Install Python 3.12–3.13, Node 20,
pnpm 9, uv, Docker, and Compose, then run:

```sh
cp .env.example .env
make bootstrap
make up
make verify
make seed
```

The app is served at `http://localhost:5173`, the API at
`http://localhost:8000`, and MailHog at `http://localhost:8025`. Host ports are
configurable in `.env` when those defaults are already occupied.

`make seed` creates access fixtures and taxonomy definitions only; it does not create fictional
company or filing data. For the governed NSE BRSR corpus, follow
[`docs/operations/NSE_BRSR_INGESTION.md`](docs/operations/NSE_BRSR_INGESTION.md). The initial
25-company command is `make ingest-nse-initial NSE_FY=2025`, and the resumable next cohort is
`make ingest-nse-next NSE_FY=2025 NSE_LIMIT=10`. Both acquisition commands publish the explicit
provisional mapping layer and rebuild Explorer; use `make publish-nse NSE_FY=2025` to rematerialize
already-ingested facts after domain review.
