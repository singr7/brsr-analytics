# PHASE 5 — Intent-led UX Revamp (S18–S23)

*The experience layer. Doctrine: useful before configurable; plain language before domain controls; evidence and expert depth always one action away.*

This phase implements [`UX-revamp.md`](../UX-revamp.md). It runs before infrastructure and launch so the final accessibility pass, production UAT, analytics funnels, and launch materials validate the intended experience. Existing infrastructure and launch work moves unchanged to S24–S25 in `PHASE6_PRODUCTION.md`.

---

## Phase outcomes

By the end of S23:

1. The portal is organised around **Explore insights**, **Analyse my BRSR**, and **Filing Studio**.
2. A new visitor reaches a meaningful, evidence-backed insight without first configuring filters.
3. Natural-language follow-ups inherit the visible analytical context and explain their interpretation.
4. A private BRSR upload produces a traceable at-a-glance analysis and a relevant peer benchmark.
5. Learning assistance is optional, contextual, measurable, and easy for experts to disable.
6. Filing Studio has a clear start/continue/import/analyse-report entry and unambiguous readiness language.
7. Old URLs remain valid; tier enforcement, suppression, lineage, privacy, and export gates remain intact.

## Cross-session constraints

- Preserve the current design tokens, chart kit, materialised-number rule, lineage rule, and governed semantic DSL.
- Use one portal and one responsive shell; modes are journeys, not separate branded products.
- New public analysis values must read only QA-pinned materialisations. Private uploaded-report findings may read the uploader's private extraction state and must be explicitly labelled as private analysis, never corpus truth.
- An analysed BRSR is private by default and never enters the public corpus without a separate explicit publication permission flow. This phase does not add such a permission flow.
- “Assurance trends” means public market adoption. “Filing readiness” means validation/evidence coverage. Formal assurance remains an independent-provider activity.
- Expert users can reach full filters or the full query workspace in one action from every guided view.
- Every session expands the route×role×tier matrix and registers its events before UI code emits them.

---

## S18 — Experience foundation, information architecture, shell, and home

**GOAL:** Replace expert-first entry with an intent-led shell and homepage while preserving every existing route and capability.

**READ:** `01_CONVENTIONS.md`, HANDOFF, `UX-revamp.md` §§1–6 and §§11–16, `frontend/src/App.tsx`, `frontend/src/components/Phase2Pages.tsx`, `frontend/src/index.css`, `frontend/src/theme/tokens.ts`, `events.yaml`.

**TASKS**

1. Write an implementation contract at `docs/ux/experience-contract.md`: primary/utility navigation, route map, canonical terms, mobile behaviour, signed-in variants, role/tier states, and an explicit old→new copy map. Treat `prototype/ux-revamp.html` as a hierarchy reference, not production code.
2. Refactor the app shell into focused components (`SiteHeader`, `UtilityNav`, `JourneyNav`, mobile menu) without changing auth/org switching. Primary nav: Explore insights, Analyse my BRSR, Filing Studio, Learn BRSR; utility: Ask BRSR Lens, Methodology, Pricing, account/sign-in.
3. Rebuild `/` around the approved headline, three intent cards, private-analysis promise, and one real preconfigured insight using the existing semantic query and chart kit. Keep source/methodology access and honest preview/error states.
4. Rename user-facing labels: Assurance→Assurance trends, Studio→Filing Studio, Ask the corpus→Ask BRSR Lens, Refine the lens→Refine this view, My benchmarks→Peer benchmarks. Do not rename stable API fields or routes solely for copy.
5. Add route aliases/canonical redirects only where needed; `/assurance`, `/studio`, `/ask`, `/library`, and saved query URLs must remain valid and indexable as appropriate.
6. Add first-party events: `home_intent_selected`, `guided_insight_viewed`, `analyse_cta_selected`, `filing_cta_selected`; include intent, auth state, plan tier, and source surface without sending report text or query text.
7. Update titles, citation metadata, skip-link/focus behaviour, responsive navigation, and active-route state. Ensure all actions have outcome-oriented accessible names.
8. Add component tests for anonymous/authenticated shell variants, all intent links, old routes, mobile menu keyboard operation, label changes, and event payload privacy.

**FIRST MEANINGFUL PREVIEW:** The new first viewport, three journeys, and real guided insight render successfully on `/`; all other routes still use the existing working pages.

**SELF-CHECK:** five-second comprehension check with 3 internal reviewers · `/`, `/sectors`, `/assurance`, `/studio`, `/ask` route smoke · header keyboard walk · mobile text/layout review · no regression in auth/org switch · `make verify` green.

**COMMITS:** `feat(ux): intent-led shell and navigation [S18]`, `feat(home): journey-led entry and live insight [S18]`, `test(ux): shell routes and entry events [S18]`, close.

**HANDOFF:** experience contract path, shell component API, route/alias table, event payloads, unresolved copy decisions.

---

## S19 — Guided Explore and contextual Ask BRSR Lens

**GOAL:** Let beginners start with useful questions while experts retain one-action access to full filters and query detail.

**READ:** HANDOFF, `UX-revamp.md` §7, experience contract, semantic DSL/catalog, `Phase2Pages.tsx`, `lib/semantic.ts`, NLQ router/service/schema, `prompts/nlq.yaml`.

**TASKS**

1. Add a versioned curated-question registry (`frontend/src/content/guided-questions.ts` or data file) with stable IDs, plain-language question, DSL, summary template, explanation, suggested follow-ups, eligible tiers, and destination view. Seed 6–8 approved questions across sector, Core, substance, materiality, and assurance trends.
2. Build `/explore` as the guided hub: question cards, active question, chart/result, human-readable cohort, key takeaway, “why this matters,” methodology/source affordances, and robust loading/empty/suppressed/error states.
3. Put advanced controls behind **Refine this view** while keeping them keyboard accessible and URL-persisted. Experts can expand filters immediately; cross-filter behaviour and shareable query state remain unchanged.
4. Create a reusable contextual `AskFollowUp` composer. It sends the current governed DSL as context, never concatenates it into the user's question, and makes inherited context visible before execution.
5. Extend `/api/nlq` request/response contracts only as needed for `base_dsl`, context merge, and provenance. Validate the merged DSL through the same semantic compiler and policy layer; user wording cannot weaken suppression or tier gates.
6. Reframe transparency UI to “I understood your question as…” and “Data included,” with expert-only query details. Ambiguity, refusal, confidence, editable chips, and save-as-view remain available.
7. Register `guided_question_selected`, `guided_filter_opened`, `guided_followup_selected`, `learn_explanation_opened`; exclude raw free-text questions from analytics and store only existing safe length/theme metadata where policy permits.
8. Add goldens for base-context merge, conflicting filters, ambiguity, adversarial suppression, suggested-follow-up execution, URL round trip, and anonymous/tier variants.

**SELF-CHECK:** a visitor reaches a result with zero filter interaction · expert reaches full controls in one action · 8 curated questions produce valid DSL · follow-up inherits visible cohort · adversarial prompt cannot escape policy · URL share reproduces view · `make verify` green.

**COMMITS:** `feat(explore): guided question registry and hub [S19]`, `feat(nlq): context-aware follow-ups [S19]`, `test(explore): guided and contextual query journeys [S19]`, close.

**HANDOFF:** curated-question schema and IDs, `/api/nlq` context contract, merge precedence rules, event payloads, query fixtures.

---

## S20 — Private BRSR analysis pipeline and report contract

**GOAL:** Turn an uploaded BRSR into a private, reproducible, evidence-linked analysis without conflating it with public corpus publication or a Studio evidence document.

**READ:** HANDOFF, `UX-revamp.md` §8, acquisition/upload service, parse/extract/score contracts, semantic benchmark service, storage service, auth/access model, privacy page/service, quota service, lineage schema.

**TASKS**

1. Define `analysis_uploads` and `analysis_reports` domain contracts and migration `0009`: org/user owner, object key/checksum, detected/confirmed company and FY, consent/authority attestations, retention state, processing stage, parser/schema/model versions, cohort definition, status, error code, timestamps, and optional Studio filing link. Store findings/components as versioned report payloads or normalised rows according to query needs; never store raw file bytes in Postgres.
2. Add authenticated endpoints: create upload session, confirm metadata/attestations, get processing state, retrieve report, request deletion, and create a Studio handoff. Every route enforces owner/org isolation; anonymous users may view the promise but cannot upload.
3. Build a dedicated worker orchestration path reusing deterministic parse/XBRL, extraction, scoring, and lineage components. Checksum-idempotent retries must not duplicate reports or usage. This path must not create public corpus records or QA pins.
4. Produce a versioned private report contract containing: separate completeness/substance/Core/evidence/readiness dimensions, status wording, top three prioritised findings, section/topic coverage, peer cohort and percentile where eligible, evidence/source refs, explicit missing-evidence markers, methodology version, limitations, and generated timestamp.
5. Build peer matching from confirmed company metadata, FY, sector, and market-cap band through the governed semantic service. Enforce minimum cohort and tier policy; return a clear “benchmark unavailable” reason rather than inventing a peer set.
6. Add privacy controls: private-by-default flag, configurable retention deadline, deletion tombstone/audit event, signed-download expiry, object deletion job, and privacy-page copy contract. Never log filenames, report text, extracted passages, or signed URLs.
7. Decide entitlement in `plans.yaml`: recommended default is one limited own-report analysis after registration, detailed peer/evidence views on Pro, and unlimited/contract quota on Studio. Implement quotas through `services/quotas.py`, not route conditionals.
8. Register `analysis_upload_started`, `analysis_metadata_confirmed`, `analysis_processing_completed`, `analysis_processing_failed`, `analysis_deletion_requested`, and safe stage/duration metadata.
9. Add API success/auth/validation/tier tests, checksum replay, malicious file/type/size tests, org isolation across every endpoint and storage key, deletion/retention tests, failure recovery, benchmark suppression, and a small offline end-to-end fixture report.

**SELF-CHECK:** upload promise and actual report contract match · private data never appears in public semantic results · org B cannot address org A's upload/report/object · identical retry creates no duplicate work · every finding is sourced or explicitly marked as absent evidence · deletion removes object and access · `make verify` green.

**COMMITS:** `feat(analysis): private upload and report domain [S20]`, `feat(worker): reproducible BRSR analysis pipeline [S20]`, `test(analysis): isolation retention and report goldens [S20]`, close.

**HANDOFF:** migration/table schema, endpoint signatures, worker stages/retry keys, report JSON schema, quota/tier matrix, retention configuration names.

---

## S21 — Analyse my BRSR journey, results, benchmark, and Studio handoff

**GOAL:** Deliver the complete user-facing `/analyse` flow from a clear pre-upload promise to an actionable report and controlled next step.

**READ:** HANDOFF, `UX-revamp.md` §8, S20 contracts, auth UI, chart kit, lineage viewer, benchmark page, Filing Studio create/import APIs, privacy copy.

**TASKS**

1. Build `/analyse` states: public promise, sign-in continuation, file selection, metadata/privacy/authority confirmation, upload, staged processing, recoverable failure, report ready, deletion requested/deleted, and expired report.
2. Make the pre-upload promise exact: accepted formats/size, outputs, processing expectations, entitlement, who can access it, corpus exclusion, retention, deletion, and methodology limitations. Require explicit attestations before upload completion.
3. Build “Your BRSR at a glance” with status wording, four separate dimensions, three priority findings, transparent peer cohort, coverage by section/Core topic, evidence-linked detail, missing-evidence states, and methodology/limitations. Do not collapse this into one score.
4. Reuse `LineageViewer` for uploaded-report evidence while enforcing private report authorization. Clearly distinguish a found source passage from “no supporting evidence found.”
5. Add **Benchmark in detail** and **Improve this filing in Filing Studio** actions. The latter shows exactly what will be copied, requires confirmation, creates/links one filing idempotently, and preserves source provenance.
6. Add report deletion and privacy controls in the result view. Deletion must invalidate visible/downloadable report state and explain what audit metadata is retained.
7. Instrument the funnel: promise viewed→sign-in→upload start→metadata confirmed→report completed/viewed→lineage opened→benchmark selected→Studio handoff. Never include report contents or identifying filenames.
8. Add component and end-to-end tests for all states, refresh/resume, keyboard and screen-reader status announcements, mobile upload, errors, tier limits, deletion, lineage authorization, and idempotent Studio handoff.

**FIRST MEANINGFUL PREVIEW:** `/analyse` shows the complete pre-upload promise and a fixture-backed result state before upload orchestration UI is broadened.

**SELF-CHECK:** user knows output/privacy before file selection · processing can survive page refresh · report prioritises action over score · peer cohort is explicit · source access works · Studio handoff is confirmed/idempotent · mobile and keyboard flow complete · `make verify` green.

**COMMITS:** `feat(analyse): private upload journey [S21]`, `feat(analyse): evidence-linked results and peer action [S21]`, `feat(studio): analysed-report handoff [S21]`, close.

**HANDOFF:** route state machine, report component interfaces, handoff contract, funnel event sequence, accessibility announcements.

---

## S22 — Contextual learning mode, scenarios, and understanding progress

**GOAL:** Add professional, optional learning assistance that explains concepts in the flow of real exploration without blocking expert work.

**READ:** HANDOFF, `UX-revamp.md` §10, Learning Library API/model, auth/profile settings, engagement events, curated-question registry, approved BRSR terminology.

**TASKS**

1. Define a versioned learning-content schema: concept ID, level, plain-language definition, why-it-matters, strong/weak pattern links, scenario question/options/explanation, source/methodology link, and applicable routes/measures. Content is reviewed data, not inline component copy or live-LLM output.
2. Seed the six approved areas: foundations, nine principles, BRSR Core, materiality/evidence, assurance basics, and filing workflow. Use scenario questions rather than trivia; link answers to Library exemplars where access permits.
3. Add **Explain as I explore** as a global preference with three states: on, off, and not yet chosen. Anonymous preference may be device-local; authenticated preference syncs to the profile. Default assistance may be visible but must be dismissible and never modal-blocking.
4. Create reusable concept help, “why this matters,” strong-vs-weak pattern, and one-question check components. Integrate first into guided Explore, analysis results, and Filing Studio labels; do not annotate every term at once.
5. Add migration `0010` and APIs for authenticated learning progress: content version, completed concept IDs, scenario attempts/result, timestamps. Store no free text. Anonymous progress remains local until explicit sign-in merge consent.
6. Build `/learn`: BRSR understanding (not competence) meter, area progress, next recommended scenario, glossary, quiz history, and Learning Library discovery. Meter reflects completed units/checks only and has no effect on access, filing readiness, or professional claims.
7. Register `learning_mode_changed`, `concept_help_opened`, `learning_scenario_answered`, `learning_unit_completed`; prevent event spam and keep answers as stable option IDs.
8. Add content-schema validation, version migration behaviour, preference sync/merge tests, accessibility tests, meter calculation goldens, professional-copy review fixture, and assurance-definition test distinguishing readiness from independent assurance.

**VALIDATION GATE:** Conduct five beginner and five sustainability-professional prototype/usability sessions. If the meter is perceived as patronising or distracts from work, ship contextual explanations and scenarios but keep `/learn` progress behind a feature flag. Do not block the rest of the UX phase.

**SELF-CHECK:** explanations are optional/dismissible · expert path is unchanged when off · meter cannot affect access/readiness · content is versioned and reviewable · anonymous data is not silently merged · assurance language passes domain review · `make verify` green.

**COMMITS:** `feat(learn): versioned contextual learning content [S22]`, `feat(learn): preferences scenarios and progress hub [S22]`, `test(learn): content progress and accessibility [S22]`, close.

**HANDOFF:** learning schema/version, profile/progress APIs, meter formula, feature flag, usability findings and go/no-go decision.

---

## S23 — Filing Studio entry alignment, migration polish, UX assurance, and rollout

**GOAL:** Complete the cross-journey experience, prove no trust or expert capability regressed, and prepare a controlled rollout before production infrastructure work.

**READ:** HANDOFF, `UX-revamp.md` §§9 and 13–16, S18–S22 contracts, Studio page/service/tests, Pricing/Billing pages, QA_PLAN, analytics/admin surfaces, BACKLOG browser items.

**TASKS**

1. Add a Filing Studio landing/start state with: start new, continue draft, import prior BRSR, and continue from analysed report. Keep plan/auth states explicit and route existing active filings directly only when the user has chosen that preference.
2. Align Studio task language: Complete the filing, Add and map evidence, Review AI suggestions, Check filing readiness, Export filing package. Explain that formal assurance is independent; remove ambiguous validation-as-assurance wording.
3. Add contextual learning hooks to the highest-friction Studio concepts, plus a clear “expert mode” path that keeps the dense existing workspace and keyboard efficiency.
4. Audit cross-route handoffs, back navigation, saved URLs, old bookmarks, metadata, pricing descriptions, empty/loading/error/locked states, and analytics funnels. Repair broken assumptions introduced by the new shell or routes.
5. Add feature flags for `intent_home`, `guided_explore`, `private_analysis`, and `learning_mode`; define cohort assignment, kill-switch behaviour, and old-home fallback. Private-analysis security fixes are never feature-flagged off in favour of unsafe behaviour.
6. Extend `/admin/analytics` with the new intent, guided-insight, analysis, learning, and Studio-handoff funnels using event IDs only. Establish pre-rollout baseline and success/guardrail metrics from `UX-revamp.md`.
7. Execute UX UAT with at least five beginners and five sustainability professionals: five-second home comprehension, first meaningful insight, contextual follow-up, upload promise/privacy comprehension, fixture report interpretation, Studio start choice, learning-mode reaction, and expert filter bypass. Record issues as P0/P1/P2 with owner.
8. Complete automated accessibility and interaction coverage: axe on every new public state; keyboard/screen-reader walks; reduced-motion/contrast; 360/768/1280 layouts; upload and charts; route×role×tier matrix; saved-URL regression; performance budgets (Home ≥85 Lighthouse, no material regression on Explore).
9. Run a 10% internal/beta rollout if an environment is available. Promote only when P0/P1=0 and guardrails hold; otherwise document the fallback/flag decision. Update methodology/privacy/help copy and support runbook.
10. Close all applicable historical frontend visual/keyboard BACKLOG items, update `QA_PLAN.md` UAT to the new journeys, write a dated UX gate note at `docs/gates/ux.md`, and hand off to S24 infrastructure with the intended route and smoke-test inventory.

**SELF-CHECK:** old links work · all primary journeys are understandable and complete · expert workflows remain one action away · no privacy/tier/suppression/lineage regression · axe has zero serious/critical findings · UAT P0=P1=0 · feature-flag rollback proven · `make verify` green.

**COMMITS:** `feat(studio): intent-led entry and readiness language [S23]`, `feat(analytics): UX funnels and rollout flags [S23]`, `test(ux): accessibility UAT and regression gates [S23]`, `chore(session): close S23 — UX handoff written`, close.

**HANDOFF:** final route inventory, smoke paths for S24/S25, enabled flags, UAT findings, accessibility/performance results, UX gate note, remaining P2 backlog.

---

## Phase dependency and migration map

| Session | Depends on | Database | Main API change | Main frontend change |
|---|---|---|---|---|
| S18 | S17 | None expected | None expected | Shell, home, terminology |
| S19 | S18 | None expected | Context-aware NLQ contract | Guided Explore, contextual Ask |
| S20 | S17 contracts; S19 optional | `0009` | Private uploads/reports/deletion/handoff | Contract fixtures only |
| S21 | S20 | None expected | Uses S20 APIs | Full Analyse journey and results |
| S22 | S18–S21 | `0010` | Preferences/progress/content | Learning mode and `/learn` |
| S23 | S18–S22 | None expected | Flags/analytics only | Studio entry, integration polish |

S19 and early S20 can overlap only if separate owners are explicitly assigned; both touch shared API schemas and event registration, so merge sequencing must be agreed first. Default execution is sequential.

## Phase-level release gates

- Product: 90% of moderated participants correctly identify all three primary journeys; median time to first meaningful insight ≤60 seconds.
- Privacy: 100% of upload-test participants understand private-by-default and corpus exclusion before file selection.
- Trust: every report finding is evidence-linked or explicitly marked as missing evidence; suppression and tier tests remain green.
- Accessibility: zero serious/critical axe findings; primary journeys complete by keyboard at 360, 768, and 1280 widths.
- Performance: Lighthouse performance ≥85 on Home; guided Explore adds no >10% p95 regression to the existing semantic query path.
- Expert guardrail: full filters and full Ask workspace reachable in one action; saved URLs round-trip unchanged.
- Delivery: `make verify` green, migration upgrade/downgrade tested, P0/P1=0, `docs/gates/ux.md` signed.

## Explicit non-goals

- No public publication opt-in for uploaded reports in this phase.
- No automatic regulatory submission.
- No claim that BRSR Lens performs independent assurance.
- No single composite “BRSR score.”
- No live-LLM-generated learning curriculum or compliance advice.
- No points, leaderboards, streak pressure, or gamification tied to plan access.
- No replacement of the semantic DSL, chart kit, scoring methodology, or existing evidence-lineage doctrine.
