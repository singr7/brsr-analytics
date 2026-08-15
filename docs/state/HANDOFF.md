# HANDOFF — after S18 (2026-08-15)

## Repo state: `main` · S18 complete · dev services up · migrations head `0008`

## Delivered

- Added `docs/ux/experience-contract.md` as the canonical navigation, copy, route, role/tier,
  responsive, and entry-event contract.
- Replaced the module-first header with `SiteHeader`, `JourneyNav`, `UtilityNav`, and an
  Escape-closing/focus-restoring mobile menu while retaining sign-in and organisation switching.
- Rebuilt `/` around Explore, Analyse, and File outcomes, an explicit private-analysis promise,
  and a QA-pinned FY25 semantic insight using the existing ranked chart and policy states.
- Added staged `/explore`, `/analyse`, and `/learn` entries; retained `/sectors`, `/assurance`,
  `/studio`, `/ask`, `/library`, `/benchmarks`, and saved semantic query URLs.
- Applied canonical S18 terms, active-route state, skip navigation, focus styling, route titles,
  citation/public URL metadata, and canonical links.
- Registered and tested four privacy-safe entry events plus anonymous/authenticated shell, routes,
  mobile keyboard behaviour, copy, query-state, and payload contracts.

## Contracts next session relies on

- Shell API: `SiteHeader({ path, tier, profile, org, onOrgChange, onSignIn, onSignOut })`;
  `JourneyNav({ path })`; `UtilityNav({ path })`.
- Route aliases: `/explore` renders the current sector view (canonical `/sectors`); `/learn` renders
  the current library (canonical `/library`); `/analyse` is the private-analysis promise.
- Home insight DSL: `completeness` by `sector`, `fy = 2025`, distribution, descending, limit 20;
  public values remain sourced through `/api/query` only.
- S18 event properties are exactly `intent`, `auth_state`, `plan_tier`, `source_surface`; raw report,
  company, organisation, query, question, and email data are prohibited.
- Event names: `home_intent_selected`, `guided_insight_viewed`, `analyse_cta_selected`,
  `filing_cta_selected`.

## Sharp edges

- `/explore` and `/learn` are intentional aliases until S19/S22 replace their staged content.
- `/analyse` deliberately promises outcomes but has no file selector; S20 owns private upload.
- The browser bridge exposed no browser instance, so desktop/mobile visual inspection is backlogged;
  responsive CSS review and mobile focus/Escape component tests passed.
- Vitest prints the existing root `@tsconfig/node16` resolution warning; checks still pass.

## Env/secrets added

- None.

## Next: S19 — Guided Explore and contextual Ask BRSR Lens

Build the curated-question registry and replace the `/explore` alias with the guided hub. Preserve
the S18 shell API, event privacy shape, canonical old routes, semantic compiler, and expert bypass.
