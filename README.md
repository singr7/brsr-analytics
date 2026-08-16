# BRSR Lens — AI-Agent Build Plan
### Production-grade BRSR analytics platform + Filing Studio + engagement engine, built in 25 self-sufficient sessions

Companion pack to the VerityGrid build plan, same operating model: executed by an AI coding agent (Claude Opus / GPT-class) one session at a time, human operator supervising; every session self-verifies (`make verify`), commits cleanly, and hands off via a structured state file. **This is an independent product on an independent, deliberately lighter stack** (see 00_ARCHITECTURE — Postgres+pgvector single-database design; no Elastic, no EO). It can later exchange data with VerityGrid through plain APIs; nothing couples them at build time.

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

## How to run a session
Identical protocol to the VerityGrid pack: fresh agent conversation + exactly three inputs — `01_CONVENTIONS.md`, the single session spec, current `docs/state/HANDOFF.md` — then: *"Execute session SNN per spec; follow the protocol exactly; end with DoD table + `make verify` output."* Human verifies, merges, moves on.

## Token strategy (same doctrine, one addition)
Handoff-file state · read-listed-files-only · vertical slices · phase-file splitting · verbs in Make. **Addition for this product:** all LLM prompts live in versioned files (`prompts/*.yaml`) with committed fixture responses for offline tests — sessions never depend on live LLM calls to pass `make verify` (live accuracy runs are nightly/manual; see QA_PLAN §4).

## Special governance gates (this product publishes numbers about named companies)
Three human gates are wired into the plan and cannot be skipped: **Editorial gate** (S07/S25 — no company-level figure goes public below the confidence threshold or without QA-sampled extraction accuracy ≥ target), **Legal gate** (S04/S25 — source acquisition terms, upload/privacy promises, and methodology reviewed before launch), and **UX gate** (S23/S25 — the intended journeys pass comprehension, accessibility, and expert-bypass checks). The agent builds the mechanisms; humans sign the gates.

## Build order at a glance
```
PHASE 0  S01 scaffold → S02 schema → S03 auth+tiers
PHASE 1  S04 acquisition+registry → S05 XBRL/PDF parsing → S06 LLM extraction+QA → S07 scoring engines
PHASE 2  S08 semantic layer → S09 design system+shell → S10 dashboards → S11 NLQ+filters → S12 lineage+library
PHASE 3  S13 questionnaire engine → S14 doc-to-draft AI → S15 exports (XBRL/PDF/gap)
PHASE 4  S16 analytics+leads → S17 tiers+billing-lite
PHASE 5  S18 shell+home → S19 guided Explore+Ask → S20 private analysis pipeline → S21 Analyse journey → S22 learning → S23 Studio alignment+UX gate
PHASE 6  S24 infra+deploy → S25 corpus+hardening+launch
```
~25 sessions. S18–S23 deliberately precede production hardening so launch UAT validates the intended information architecture, upload privacy flow, accessibility, and analytics funnels rather than a superseded shell.

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
`make ingest-nse-next NSE_FY=2025 NSE_LIMIT=10`.
