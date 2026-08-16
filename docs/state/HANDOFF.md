# HANDOFF — pre-production review and remediation (2026-08-16)

## Repo state: `main` · 50 FY25 NSE companies seeded locally · migrations head `0011` · `make verify` green

## Delivered by the review pass

- Replaced magnitude-based turnover scale inference with a reviewed fail-closed per-issuer
  registry, correcting Coal India from INR 14,337 crore to INR 1,43,369 crore and its energy
  intensity from 1,331.68 (second-worst) to 133.17 (mid-cohort).
- Retained XBRL `decimals` on raw facts and established that it cannot recover reporting scale.
- Production settings now reject `AUTH_EXPOSE_VERIFICATION_TOKEN=true` and `LLM_PROVIDER=fake`.
- Added identity-based plausibility screens and full multi-pin metric lineage.
- Fixed compose dev/prod parity: mailhog ports, and `taxonomy`/`scoring.yaml`/`plans.yaml`/`worker`
  mounts that had left api and worker serving stale baked config.
- Created the three mandatory unsigned launch gates under `docs/gates/`.
- Lowered the cohort suppression minimum from 8 to 5.

## Delivered by the preceding ingestion session

- Replaced the fictional 20-company seed corpus with a fail-closed official NSE BRSR importer.
- Seeded 25 NIFTY 50 companies for FY 2024–25: 25/25 filings parsed, zero missing/errors,
  and 55,105 losslessly persisted raw XBRL facts.
- Added persistent ingestion runs and registry cursor state, plus the `next --limit 10` command.
- Added configurable Celery Beat refresh and a platform-admin inventory at `/admin/ingestion`.
- Documented source policy, commands, exact seeded tickers, scheduler controls and persistence in
  `docs/operations/NSE_BRSR_INGESTION.md`.
- Published 400 explicitly provisional mapped fields across 25 FY25 filings, producing 425 metrics
  and 75 method-versioned scores with source-fact lineage.
- Added common-unit energy/water/emissions conversions, registry-resolved turnover scale,
  Scope 1+2 totals, and three per-INR-crore intensities.
- Added five real-data Explorer questions and an Admin mapping review workflow with assumptions,
  confidence, accept/needs-review/reject status and reviewer notes.

## Existing S19 contracts

- Added the versioned `frontend/src/content/guided-questions.ts` registry with eight stable guided
  questions, approved DSL, explanation, follow-ups, tier eligibility, and expert destinations.
- Replaced the `/explore` alias with a guided hub: zero-config result, current cohort, takeaway,
  honest states, sources, tier locks, responsive question grid, and one-action advanced controls.
- Persisted the active question and refined DSL in `?question=<id>&q=<json>` while retaining all
  canonical expert routes and the full `/ask` workspace.
- Added reusable `AskFollowUp`; contextual NLQ sends `question` and `base_dsl` separately and shows
  inherited context before and after execution.
- Extended `/api/nlq` with merge provenance. Follow-up filters override the same base dimension;
  non-conflicting base filters inherit. The merged DSL uses the existing semantic validator,
  tier/cohort policy, compiler, execution, and lineage path.
- Registered four S19 events and removed raw question text from `nlq_asked` analytics.

## Contracts next session relies on

- Registry version: `1.0.0`; 13 questions. Original IDs: `sector-completeness-fy25`, `substance-by-sector`,
  `core-readiness-gaps`, `materiality-evidence`, `assurance-trend`, `market-cap-quality`,
  `company-scope3`, `boilerplate-watch`.
- FY25 NSE IDs: `company-energy-fy25`, `company-water-fy25`,
  `company-energy-intensity-fy25`, `company-water-intensity-fy25`, and
  `company-emissions-intensity-fy25`.
- `/api/nlq` request: `{ question: string, base_dsl?: SemanticQuery }`.
- `/api/nlq` response adds `context: { applied, inherited_filters, overridden_filters }`.
- Merge precedence: translated filters replace base filters with the same `dimension`; remaining
  base filters are inherited. Translated measures, dimensions, shape, sort, and limit are explicit.
- S19 event names: `guided_question_selected`, `guided_filter_opened`,
  `guided_followup_selected`, `learn_explanation_opened`. No raw question or DSL text is allowed.
- `/explore` is now canonical to itself. `/sectors` remains the canonical detailed sector surface.

## Sharp edges

- Turnover scale is resolved from the reviewed `turnover_scale.issuers` registry in
  `taxonomy/nse_concept_mappings.yaml`, never inferred from magnitude. Any new issuer reporting
  below the 1e9 absolute threshold needs a registry entry with evidence, or its turnover and all
  turnover-normalized intensities are withheld. `publish` reports these as `withheld=<n>`.
- The XBRL `decimals` attribute is precision, not scale, and must never be used to infer scale.
- Migration `0010` narrows the published-number rule to allow provisional NSE pins on public
  surfaces. This is an open decision in `docs/gates/editorial.md`.
- `MtCO2e` is still provisionally read as metric tonnes (confidence 0.80); first review priority.
- Cohort minimum is 5, and thin cohorts are shown with a footnote rather than blanked. 12 of 15
  sector cohorts are below 5, some at n=1 where the aggregate is that company's own value.
  Sector percentiles are still withheld below the minimum. Open in `docs/gates/editorial.md`.
- `scoring.yaml` and `plans.yaml` are single-file bind mounts, which pin an inode: restart the
  api/worker/scheduler services after editing them or the containers keep the old content.
- Batch 1 `xbrl_facts` rows predate the `decimals` column and are null until re-ingested; batch 2
  rows carry it. No published number depends on it.
- Any new issuer reporting turnover below 1e9 needs a `turnover_scale` registry entry or it is
  withheld. `JIOFIN` is registered at confidence 0.70 and wants domain review.
- The assurance guided question uses the governed `assurance_readiness` timeseries as an
  explicitly labelled proxy; public assurance adoption detail remains on `/assurance`.
- The browser runtime still exposes no browser instance, so the visual/keyboard passes listed in
  `docs/state/BACKLOG.md` remain outstanding and `docs/gates/ux.md` cannot be signed.

## Env/config added

- `SOURCE_NSE_BRSR_ENABLED` (fail-closed; default `false`)
- `NSE_BRSR_CONTACT`, portal/registry URLs, default FY and batch size
- `NSE_BRSR_SCHEDULE_ENABLED` and `NSE_BRSR_REFRESH_HOURS`
- `MAILHOG_SMTP_PORT` and `MAILHOG_UI_PORT` (host-side only; default 1025/8025)
- No new secrets. `AUTH_EXPOSE_VERIFICATION_TOKEN` and `LLM_PROVIDER` are now production-validated.

## Next

Sign or reject the three gates in `docs/gates/`. The editorial gate carries two open decisions:
provisional NSE pins on public surfaces, and the cohort minimum of 5. Then have domain owners
review the 16 mappings in `/admin/ingestion`, starting with `MtCO2e`. `compose.prod.yml` and the
empty `infra/{terraform,cloudinit,deploy}` trees are the largest remaining gap before turn-up.
