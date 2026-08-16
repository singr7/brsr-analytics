# HANDOFF — NSE BRSR corpus ingestion (2026-08-16)

## Repo state: `main` · real NSE corpus seeded locally · migrations head `0009`

## Delivered this session

- Replaced the fictional 20-company seed corpus with a fail-closed official NSE BRSR importer.
- Seeded 25 NIFTY 50 companies for FY 2024–25: 25/25 filings parsed, zero missing/errors,
  and 55,105 losslessly persisted raw XBRL facts.
- Added persistent ingestion runs and registry cursor state, plus the `next --limit 10` command.
- Added configurable Celery Beat refresh and a platform-admin inventory at `/admin/ingestion`.
- Documented source policy, commands, exact seeded tickers, scheduler controls and persistence in
  `docs/operations/NSE_BRSR_INGESTION.md`.

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

- Registry version: `1.0.0`; IDs: `sector-completeness-fy25`, `substance-by-sector`,
  `core-readiness-gaps`, `materiality-evidence`, `assurance-trend`, `market-cap-quality`,
  `company-scope3`, `boilerplate-watch`.
- `/api/nlq` request: `{ question: string, base_dsl?: SemanticQuery }`.
- `/api/nlq` response adds `context: { applied, inherited_filters, overridden_filters }`.
- Merge precedence: translated filters replace base filters with the same `dimension`; remaining
  base filters are inherited. Translated measures, dimensions, shape, sort, and limit are explicit.
- S19 event names: `guided_question_selected`, `guided_filter_opened`,
  `guided_followup_selected`, `learn_explanation_opened`. No raw question or DSL text is allowed.
- `/explore` is now canonical to itself. `/sectors` remains the canonical detailed sector surface.

## Sharp edges

- The assurance guided question uses the governed `assurance_readiness` timeseries as an explicitly
  labelled proxy; public assurance adoption detail remains on `/assurance`. Do not conflate them.
- The current `SmartFilters` exposes FY and market-cap band; registry DSL and full expert pages retain
  the broader query surface until later guided-control expansion.
- Existing ECharts component mocks print ref warnings and Vitest prints the root tsconfig warning;
  both predate S19 and checks pass.
- The browser runtime exposed no browser instance. Live HTTP, responsive CSS, component interaction,
  URL, keyboard-native control, and production-build checks passed; visual inspection is backlogged.

## Env/config added

- `SOURCE_NSE_BRSR_ENABLED` (fail-closed; default `false`)
- `NSE_BRSR_CONTACT`, portal/registry URLs, default FY and batch size
- `NSE_BRSR_SCHEDULE_ENABLED` and `NSE_BRSR_REFRESH_HOURS`

## Next

Map the live NSE taxonomy concepts into governed `field_defs`, run QA/pinning, and rebuild public
metrics. Raw facts exist now, but ingestion intentionally does not auto-publish unmapped values.
