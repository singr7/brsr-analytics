# QA_PLAN.md — BRSR Lens
### Quality strategy for a product that publishes numbers about named companies and helps them file regulatory documents. The bar is set accordingly.

## 1. Principles
1. **`make verify` green is the only closing condition** — lint+typecheck+all offline tests; never a red handoff.
2. **Offline-first, LLM included.** No test touches network, AWS, or a live LLM. Prompts ship with fixture responses (`prompts/fixtures/`); the FakeLLM serves them; `@live` marks manual/nightly accuracy runs. A test that would call a live model *fails CI by design*.
3. **Two truths, two harnesses.** *Engineering truth* (does the code work) via the pyramid below; *content truth* (are the published numbers right) via the extraction benchmark + QA sampling protocol (§4) — different machinery, both gating.
4. **Policy lives in one place and is tested there.** Suppression/anonymisation (celebrate-by-name/critique-by-cohort), tier gating, and publish gating are enforced in the semantic layer and pin mechanism — adversarial tests attack them there, and NLQ/prompt-injection tests prove the LLM cannot route around them.

## 2. Test pyramid & budgets
| Layer | Tooling | Expectation | Runtime |
|---|---|---|---|
| Unit | pytest + hypothesis | services/worker ≥ 85%; extraction/scoring/semantic/leads ≥ 95% | < 90 s |
| API integration | pytest+httpx on compose | every endpoint: success + auth-fail + validation-fail; tier variants | < 3 min |
| Worker integration | pytest + celery | every task: happy + retry + idempotent replay | < 3 min |
| Frontend | vitest + Playwright + axe | auth, dashboards, NLQ loop, lineage, Studio walk, exports | < 6 min |
| Pipeline test (§5.1) | full stack, fixtures | filing→parse→extract→QA-pin→metrics→dashboard→lineage, one path | < 4 min |
| Nightly | live LLM accuracy (extraction bench + NLQ goldens), corpus reconciliation, dep audit | — | CI-nightly |

## 3. Fixture strategy
`testdata/` (small, reviewed): 2 synthetic XBRL instances (valid + one with unit traps); 4 constructed PDFs — clean BRSR, messy (mid-page start, renamed headings), trap (BRSR-like but incomplete → locator must report ambiguity), table-heavy (for vision path); Studio doc-pack (5 small docs: policy, HR sheet, utility bill, prior BRSR, irrelevant decoy); seeded event timelines for lead-scoring goldens. Large/many-page fixtures via `make fetch-testdata`. **Truth is external:** every golden value carries a comment saying how it was computed (hand math, spreadsheet, arelle output) — the system is never tested against itself. Seed corpus (S02) includes deliberate template-twin companies (boilerplate detector target), an outlier, and small-sector cohorts (min-n suppression target).

## 4. Content-truth protocol (the editorial gate's evidence)
- **Golden extraction set:** ≥ 400 hand-verified field values across ≥ 25 real filings (built during S06/S25 QA sampling; stratified: field family × XBRL/PDF × table/narrative). Stored with page refs; grows with every human correction.
- **Benchmark:** `make bench-extraction` (fixtures, CI) + nightly live run; metric = field-level exact-match (numeric tolerance where units convert). **Publish targets: ≥ 98% per family for public exposure; 95–98% → Tier-B-gated with confidence flags; < 95% → not shown, family listed on methodology page as in-progress.** The pin policy (S06) encodes these; `/admin/quality` displays them; the S25 editorial gate signs them.
- **QA sampling in production:** per-family stratified samples at corpus-run time (sample sizes: ≥ 30 per family or 10%, whichever larger, biased toward low-confidence band); public "report an issue" (S12) feeds the same queue; corrections re-benchmark monthly.
- **NLQ goldens:** 25 translation + 8 ambiguity + 8 adversarial fixtures (S11); nightly live pass-rate tracked; < 85% live → NLQ shows lower-confidence UX (interpretation-first mode) until prompts retuned.

## 5. Named non-negotiable tests (created in sessions; nobody deletes)
1. **Pipeline test** (assembled S07, extended S12): fixture filing through to a dashboard number with working lineage modal — the demo as a test.
2. **Pin integrity** (S02): unreviewed new versions never move public values; rebuild-metrics determinism (S07).
3. **Route×role×tier authz matrix** (grows every session; completed S25).
4. **Org isolation** (S03/S14): parametrised over every retrieval path incl. Studio vector search — org B never sees org A.
5. **Suppression holds under NLQ attack** (S11): "show bottom 5 by name" and friends → cohort-anonymised output, proven at the semantic layer.
6. **Verbatim-quote tripwires** (S06/S14): fabricated citations → zeroed confidence + flag.
7. **Export block matrix** (S15): every blocking condition (validation error, arelle error, unreviewed-AI required field) individually prevents export.
8. **Lead-engine goldens + opt-out absolutism** (S16): constructed timelines → expected scores/routes; opted-out org can never be routed (property test).
9. **Rollback + restore drills** (S24/S25): executed with dated logs in `ops/drills/`.
10. **Schema-linter** (S13): the BRSR encode stays internally consistent (relations reference real fields, concepts covered) — the Studio's structural conscience.

## 6. UAT script (S23 UX gate; repeated on production in S25, two humans, ~3 h)
1. Anonymous: identify Explore/Analyse/File journeys → open a guided question without filters → inspect source/methodology → reach full filters in one action → old sector/company URLs still work.
2. Ask BRSR Lens: contextual follow-up inherits the visible cohort; 6 scripted questions (2 clean, 2 ambiguous → chips, 1 out-of-scope → graceful, 1 adversarial → suppressed); edit-chips re-run; save-as-view URL shared to second browser reproduces exactly.
3. Analyse: understand privacy/output before selection → upload fixture → confirm metadata/authority → refresh during processing → interpret separate report dimensions and top findings → inspect one evidence source and one missing-evidence state → open peer benchmark → confirm idempotent Filing Studio handoff → delete report.
4. Learning: enable/disable Explain as I explore → answer one scenario → verify BRSR understanding meter changes only learning progress and never access/readiness; expert mode remains undisturbed.
5. Pro flows: build a peer set, export board PDF, verify suppression note where cohort small.
6. Studio: select new/continue/import/analysed-report entry → create filing → import prior-year prefills → upload the doc-pack → review AI proposals (accept/edit/reject) → document-gap report sensible → seed 3 validation errors → fix via findings panel → export blocked until AI-unreviewed cleared → final export: arelle-clean XBRL + draft PDF/DOCX + gap report with the Bioedge page reading contextually, not template-ly.
7. Engagement: gap-panel visits (×3) + gap report → lead fires → context-card email arrives at test BD inbox and *reads well*; deep-dive request → ticket created; opt-out → verify silence.
8. Ops: no-op deploy rollback drill; induced extraction-worker kill mid-batch → resume completes without duplicates.
Outcome log: P0 (blocks launch) / P1 (fix before real users) / P2+ BACKLOG'd with owner. Launch requires P0=P1=0 **and all three §7 human gates**.

## 7. Gates summary
| Gate | Enforced by |
|---|---|
| verify, coverage floors, secret/vuln scans, fixture-only LLM | CI, every push |
| Golden/score-config changes are conscious (test diff + rationale in commit) | Human PR review |
| Session DoD + handoff | Operator acceptance |
| **Editorial gate** (accuracy targets, §4) | Human sign-off, `docs/gates/editorial.md` |
| **Legal gate** (sources, methodology, private-analysis privacy/retention, Studio liability) | Counsel sign-off, `docs/gates/legal.md` |
| **UX gate** (journey comprehension, accessibility, expert bypass, upload privacy) | Human sign-off in S23; deployed-build reconfirmation in S25, `docs/gates/ux.md` |
| Infra apply, deploy trigger, drills, corpus runs | Human, deliberately |
