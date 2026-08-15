# BRSR Lens experience contract

Status: S18 implementation contract (2026-08-15)

## Navigation and route map

The product is one portal with three journeys. `Learn BRSR` is a contextual aid and hub, not a
separate product. Journey navigation is always visible on desktop and available from one labelled
menu button on mobile.

| Navigation label | Canonical destination | S18 behaviour |
|---|---|---|
| Explore insights | `/explore` | Guided-entry alias to the existing sector insight until S19 expands it |
| Analyse my BRSR | `/analyse` | Public privacy/value promise; the upload pipeline arrives in S20 |
| Filing Studio | `/studio` | Existing authenticated filing workspace |
| Learn BRSR | `/learn` | Alias to the existing Learning Library until S22 expands it |
| Ask BRSR Lens | `/ask` | Existing full governed-query workspace |
| Methodology | `/methodology` | Existing public method and coverage page |
| Pricing | `/pricing` | Existing public plan page |

Existing `/sectors`, `/companies`, `/materiality`, `/assurance`, `/benchmarks`, `/ask`, `/library`,
and `/studio` URLs remain valid. Query strings, including saved semantic query state, are preserved.
The old detail routes stay indexable; aliases use a canonical link for their eventual canonical URL
without forcing a navigation or discarding query state.

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

Report names/text, uploaded content, natural-language questions, semantic query text, company names,
emails, and organisation names are prohibited in these event payloads.
