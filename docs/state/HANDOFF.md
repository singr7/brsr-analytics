# HANDOFF — after S19 (2026-08-15)

## Repo state: `main` · S19 complete · dev services up · migrations head `0008`

## Delivered

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

## Env/secrets added

- None.

## Next: S20 — Private BRSR analysis pipeline and report contract

Build migration `0009`, private analysis upload/report/storage contracts, isolated API and worker
orchestration, retention/deletion, quota policy, and fixture report. Preserve the S19 semantic,
context, tier/cohort, event-privacy, and public-corpus separation contracts.
