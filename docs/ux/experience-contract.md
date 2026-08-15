# BRSR Lens experience contract

Status: S19 implementation contract (2026-08-15)

## Navigation and route map

The product is one portal with three journeys. `Learn BRSR` is a contextual aid and hub, not a
separate product. Journey navigation is always visible on desktop and available from one labelled
menu button on mobile.

| Navigation label | Canonical destination | S18 behaviour |
|---|---|---|
| Explore insights | `/explore` | Canonical guided-question hub; expert detail remains one action away |
| Analyse my BRSR | `/analyse` | Public privacy/value promise; the upload pipeline arrives in S20 |
| Filing Studio | `/studio` | Existing authenticated filing workspace |
| Learn BRSR | `/learn` | Alias to the existing Learning Library until S22 expands it |
| Ask BRSR Lens | `/ask` | Existing full governed-query workspace |
| Methodology | `/methodology` | Existing public method and coverage page |
| Pricing | `/pricing` | Existing public plan page |

Existing `/sectors`, `/companies`, `/materiality`, `/assurance`, `/benchmarks`, `/ask`, `/library`,
and `/studio` URLs remain valid. Query strings, including saved semantic query state, are preserved.
The old detail routes stay indexable; `/learn` uses a canonical link for its eventual canonical URL
without forcing a navigation or discarding query state.

## Guided Explore and contextual Ask

The curated registry is `frontend/src/content/guided-questions.ts`, version `1.0.0`. Its stable IDs
are `sector-completeness-fy25`, `substance-by-sector`, `core-readiness-gaps`,
`materiality-evidence`, `assurance-trend`, `market-cap-quality`, `company-scope3`, and
`boilerplate-watch`. Every entry owns its question, governed DSL, summary template, explanation,
follow-ups, eligible tiers, and expert destination.

`/explore?question=<id>&q=<encoded DSL>` reproduces the active question and refined query. Curated
selection resets to that question's approved DSL; advanced filter changes update `q`. The default
view shows a human-readable cohort, takeaway, limitation-aware explanation, sources, and explicit
loading, empty, suppressed, locked, and error states. `Refine this view` and the full Ask workspace
are each available in one keyboard action.

Contextual follow-ups post `{ question, base_dsl }` to `/api/nlq`. These fields remain separate;
the question is never rewritten to contain the DSL. Translation filters override base filters for
the same dimension and all other base filters are inherited. The response `context` object reports
`applied`, `inherited_filters`, and `overridden_filters`. The merged query always returns through
the catalog validator, tier policy, cohort suppression, compiler, and lineage path.

## Shell behaviour

- `SiteHeader` owns the brand, `JourneyNav`, `UtilityNav`, account controls, and `MobileMenu`.
- Desktop journey and utility navigation are separate labelled landmarks. Active destinations expose
  `aria-current="page"`, including their retained detail-route families.
- At 900 px and below, desktop navigation is replaced by a menu button. The menu closes on Escape,
  returns focus to its trigger, and uses ordinary links so browser navigation remains dependable.
- A keyboard-visible skip link targets `#main-content`; route headings receive programmatic focus on
  browser history navigation. Sticky navigation does not cover focused content.
- Signed-out users see **Sign in**. Signed-in users retain personal/organisation switching, plan and
  licence state, **Peer benchmarks**, and **Sign out**. Grace and read-only states remain explicit.

## Canonical language

| Old copy | New copy |
|---|---|
| Assurance | Assurance trends |
| Studio | Filing Studio |
| Ask the corpus | Ask BRSR Lens |
| Refine the lens | Refine this view |
| My benchmarks | Peer benchmarks |
| Explore sector scorecards | Explore live insights |
| A governed query out | Evidence-backed answer |
| Leading-sector completeness score | Highest sector completeness |

Stable API fields, semantic measure names, stored query state, and route paths are not renamed.
`Assurance trends` means public adoption; `filing readiness` means a company's validation and evidence
coverage; neither implies formal assurance by BRSR Lens.

## Home and entry states

The home first viewport uses the approved headline and actions for Explore, Analyse, and File. Three
intent cards repeat those outcomes without persona onboarding. The analysis promise says **private by
default** before selection. A preconfigured FY25 sector-completeness query reads only the governed
semantic endpoint and renders the existing chart kit. Loading, suppression, empty, and API-error
states remain explicit; preview fixture values are labelled as preview and never presented as live.

## Roles and tiers

| State | Shell and entry behaviour |
|---|---|
| Anonymous | All public journeys visible; analysis and Studio explain sign-in at the destination |
| Signed-in Explore | Organisation selector retained; paid capabilities remain labelled, not hidden |
| Pro | Peer benchmarks available; Studio destination remains visible with its own access handling |
| Studio / Research | Full shell plus organisation licence state; no navigation forks or rebranding |
| Grace / read-only | State shown beside the current plan; existing service enforcement is unchanged |
| Platform admin | Account quality-review route and existing admin routes remain available |

## Event contract and privacy

S18 entry events carry only `{ intent, auth_state, plan_tier, source_surface }`. `intent` is one of
`explore`, `analyse`, or `file`; `auth_state` is `anonymous` or `authenticated`; `source_surface` is a
stable UI identifier such as `home_hero`, `home_intent_card`, or `home_guided_insight`.

- `home_intent_selected`: any home journey selection.
- `guided_insight_viewed`: the real guided preview becomes visible.
- `analyse_cta_selected`: an Analyse entry is selected.
- `filing_cta_selected`: a Filing Studio entry is selected.
- `guided_question_selected`: stable guided question ID plus auth/tier/surface.
- `guided_filter_opened`: stable guided question ID and surface.
- `guided_followup_selected`: stable question/follow-up IDs, surface, and safe question length.
- `learn_explanation_opened`: stable guided question ID and surface.

Report names/text, uploaded content, natural-language questions, semantic query text, company names,
emails, and organisation names are prohibited in these event payloads.
