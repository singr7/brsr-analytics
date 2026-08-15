# BRSR Lens UX revamp plan

Status: product and UX proposal for review  
Prototype: [`prototype/ux-revamp.html`](prototype/ux-revamp.html)
Implementation sessions: [`sessions/PHASE5_UX_REVAMP.md`](sessions/PHASE5_UX_REVAMP.md)

## 1. Executive verdict

The portal does need a UX change, but it does **not** need a wholesale visual redesign or a new product strategy.

The current product has the right capabilities: sector and company insights, evidence lineage, peer benchmarking, natural-language query, a learning library, and a Filing Studio. The problem is that the navigation exposes these as expert-level product modules before a new visitor understands what BRSR Lens can do for them.

The resulting first impression is “a BRSR analytics database for people who already know the vocabulary.” The intended impression should be:

> “I can understand BRSR, explore credible insights immediately, upload my report to see where I stand, and get help preparing the next filing.”

The recommended change is therefore an **experience-layer reorganisation**:

1. Lead with user intent, not BRSR terminology.
2. Let visitors explore useful preconfigured questions before asking them to configure filters.
3. Make “upload my BRSR” a primary journey with a clear value exchange.
4. Place natural-language query inside the exploration flow, not only in a separate expert tool.
5. Add an optional learning mode that explains concepts in context and rewards progress without trivialising compliance.
6. Present Filing Studio as the filing-help workspace; separate it clearly from public “assurance trends.”

## 2. What is working and should remain

The following parts should be preserved:

- The editorial, institutional visual language: warm paper, deep green, serif display type, restrained saffron accents.
- Evidence lineage and “show the source” behaviour. This is a strong trust differentiator.
- The governed query model, explicit suppression explanations, and transparent “what I ran” view.
- Existing insight surfaces: sector scorecards, company analysis, peer benchmarking, materiality, and assurance adoption.
- Filing Studio's three-pass model: complete, add evidence, validate/export.
- The principle that AI proposes and humans approve.
- Shareable filtered views and board-ready exports.

This plan changes the way people **enter and move through** these capabilities, not the underlying analytical doctrine.

## 3. Current UX diagnosis

### 3.1 Navigation starts with domain nouns

The primary navigation currently begins with “Sectors,” “Companies,” “Materiality,” and “Assurance.” These are meaningful to a proficient practitioner, but they do not answer a first-time user's question: “What can I accomplish here?”

“Assurance” is especially ambiguous. In the current product it is a public tracker of assurance adoption, while the Filing Studio also contains assurance-readiness and gap-report concepts. A new user can reasonably interpret the top-level tab as assurance services, filing validation, or a technical definition.

### 3.2 The home page demonstrates authority, not personal usefulness

“See the substance behind sustainability reporting” is credible positioning, but the next step is “Explore sector scorecards.” That suits a research-oriented visitor and underserves two other high-value intents:

- “I have a BRSR; tell me what it says and how it compares.”
- “I need to prepare or improve our filing.”

### 3.3 Exploration asks users to understand the model too early

The current smart filters expose financial year, market-cap bands, measures, and score concepts. These are useful controls for serious analysts, but beginners need curated questions and plain-language takeaways before they need a query builder.

### 3.4 Natural-language query is separated from the moment of curiosity

“Ask the corpus” is a distinct route and is framed in system language (“a governed query out”). The trust explanation is valuable, but the query box should also appear where a chart naturally creates the next question, with suggested prompts based on the current view.

### 3.5 Learning is a library, not yet a learning experience

The Learning Library contains useful patterns, but it requires a user to choose to leave exploration and search. Beginners benefit more from short explanations attached to the insight in front of them, with the library as the deeper destination.

### 3.6 Upload is buried inside a gated filing workflow

The existing Studio accepts supporting evidence after sign-in. There is no obvious public promise that says: upload your BRSR and receive an initial report, peer position, gaps, and a route into filing preparation. This should be one of the clearest product conversion journeys.

## 4. Target experience model

Use one portal with three modes. Do not create three separate products.

| Mode | User intent | Immediate value | Natural next step |
|---|---|---|---|
| Explore | “Show me what BRSR data can reveal.” | Curated insights with beginner-friendly explanations | Refine, ask a follow-up, save a view |
| My report | “Analyse our BRSR and benchmark us.” | Upload-to-insight report with evidence and peers | Fix gaps or open Filing Studio |
| File | “Help me prepare or improve our filing.” | Guided completion, evidence mapping, readiness checks | Validate and export |

“Learn” is a toggle available across all three modes, not an isolated fourth product.

## 5. Proposed information architecture

### Primary navigation

- **Explore insights**
- **Analyse my BRSR**
- **Filing Studio**
- **Learn BRSR**
- Search / **Ask BRSR Lens**

Utility navigation:

- Methodology
- Pricing
- Sign in / organisation switcher

### Secondary exploration categories

Keep the current analytical surfaces, but demote them from primary navigation into guided exploration:

- Sectors
- Companies
- Topics and materiality
- Assurance trends
- Peer benchmarks

Rename the existing top-level “Assurance” destination to **Assurance trends** and add the descriptor “How independent assurance adoption varies across companies and sectors.” Use **Filing readiness** inside Studio for the company's own validation and evidence gaps. This removes the semantic collision.

### Suggested route mapping

| Current route | Proposed role |
|---|---|
| `/` | Intent-led home and guided insight preview |
| `/sectors`, `/companies`, `/materiality`, `/assurance` | Retained as indexable detail views under Explore |
| `/ask` | Retained as a full query workspace; query entry is also embedded throughout Explore |
| `/benchmarks` | “Peer benchmark” step within My report, with a reusable standalone view |
| `/library` | Learn hub; its content also appears contextually in insight cards |
| `/studio` | Clearly named Filing Studio, entered after filing-help CTA or report analysis |
| New `/analyse` | Upload, consent, processing state, report summary, and next steps |
| New `/learn` | Learning path, knowledge meter, quiz history, glossary, and library |

## 6. Reimagined home page

### First viewport

The first viewport should do four jobs:

1. Explain the product in plain language.
2. Let the visitor choose an intent.
3. Demonstrate a real insight without configuration.
4. Make upload and natural-language exploration immediately visible.

Recommended headline:

> Understand the filing. See where you stand. Improve what comes next.

Recommended supporting copy:

> Explore evidence-backed BRSR insights across Indian companies, or upload your report for a private gap and peer analysis.

Primary actions:

- **Explore live insights**
- **Analyse my BRSR**

Supporting action:

- **Prepare a filing**

### Intent cards

Show three compact cards immediately below or beside the hero:

- **I’m exploring BRSR** — Start with guided questions and plain-English explanations.
- **I have a BRSR report** — Upload privately; receive scores, evidence gaps, and a peer benchmark.
- **I’m preparing a filing** — Complete the format, map supporting documents, validate, and export.

These should deep-link directly into the appropriate mode. Do not ask the user to pick a persona or complete onboarding before they see value.

### Guided insight preview

Replace “six sector tiles” as the main demonstration with a story-led insight card:

- A plain-language question: “Which sectors disclose the most complete BRSR information?”
- A preconfigured chart.
- One highlighted takeaway.
- A “Why this matters” explanation.
- Source and methodology links.
- Suggested follow-ups.

Sector tiles may remain lower on the page for searchability and quick access.

## 7. Explore experience

### Start with curated questions

Offer 6–8 high-value question cards before the complete filter system, for example:

- Which sectors are most complete this year?
- What do leading companies disclose about Scope 3?
- Where are BRSR Core evidence gaps most common?
- How quickly is independent assurance adoption growing?
- How does reporting quality vary by market-cap band?
- What distinguishes substantive disclosure from boilerplate?

Each card launches a preconfigured view. Filters remain available under **Refine this view**.

### Progressive disclosure for controls

Default view:

- Active question
- Result
- Key takeaway
- Current cohort in human-readable text
- 2–3 suggested follow-ups

Expanded “Refine this view” drawer:

- Financial year
- Sector / industry
- Market-cap band
- Company cohort
- Measure
- Assurance status

The existing query chips and shareable URL behaviour should remain.

### Contextual natural-language query

Place an “Ask a follow-up” composer below the insight. Prefill suggested questions from the current context, such as:

- “Compare this with FY 2024.”
- “Show only large-cap energy companies.”
- “What explains the difference?”

On execution, retain the current transparency panel, but rewrite its labels:

- “I understood your question as…” instead of “What I ran.”
- “Data included” instead of raw filter terminology by default.
- “View query details” for expert users.

The full `/ask` route remains useful for open-ended work and saved analyses.

## 8. Analyse my BRSR journey

This is a new, prominent journey and should be distinct from uploading supporting evidence inside Filing Studio.

### Public promise

Before sign-in or upload, state exactly what the user receives:

- Disclosure completeness and substance overview
- BRSR Core and evidence coverage
- Sector and market-cap peer position
- Priority gaps with source references
- Optional route into Filing Studio

Also state the privacy model in plain language before the file picker: who can access the report, whether it enters the public corpus, retention, and how deletion works. Default to private and do not imply publication permission.

### Flow

1. Choose or drag a BRSR PDF.
2. Confirm company, reporting year, privacy, and authority to upload.
3. Show staged processing with useful labels: reading the report, matching disclosures, checking evidence, building peer cohort.
4. Land on a “Your BRSR at a glance” report, not a technical job-complete page.
5. Offer two next steps: **Benchmark in detail** and **Improve this filing in Studio**.

### Results hierarchy

1. Overall status in words, not only a score.
2. Three most important findings.
3. Peer position and cohort definition.
4. Coverage by BRSR section / Core topic.
5. Evidence-linked details.
6. Methodology and limitations.

Do not show a single opaque “BRSR score.” Preserve separate completeness, substance, assurance/readiness, and evidence dimensions.

## 9. Filing Studio positioning and flow

Rename generic references to “Studio” as **Filing Studio** in all user-facing navigation.

Position it as:

> A guided workspace to prepare, evidence-check, validate, and export a BRSR filing.

Keep the existing three passes but make the starting choices clearer:

- Start a new filing
- Continue a draft
- Import last year’s BRSR
- Continue from an analysed report

Within the workspace, use task language:

- Complete the filing
- Add and map evidence
- Check filing readiness
- Review AI suggestions
- Export filing package

Avoid using “assurance” as a synonym for validation. “Assurance-ready” may be shown as an outcome only when accompanied by a short explanation that formal assurance is performed by an independent provider.

## 10. Learn mode and knowledge meter

### Recommendation

Add this feature, but keep it optional, professional, and lightweight. A childish points-and-badges system would undermine the institutional tone.

### Learn-mode toggle

Offer **Explain as I explore** near the page title or user menu. When on, it adds:

- Plain-language definitions on first use
- “Why this matters” annotations
- Examples of strong versus weak disclosure
- One-question knowledge checks after meaningful interactions

### Knowledge meter

Call it **BRSR understanding**, not a score of the user’s professional competence.

Possible areas:

- BRSR foundations
- Nine principles
- BRSR Core
- Materiality and evidence
- Assurance basics
- Filing workflow

Progress should reflect completed learning units and successful knowledge checks. It must not affect analytics or filing access.

### Quiz mode

Use short scenario questions, not trivia. Example:

> A company publishes a net-zero target but does not state its baseline year or boundary. What is missing?

After the answer, show the explanation and link directly to a relevant anonymised filing example. Allow users to skip, dismiss, or turn learning mode off permanently.

## 11. Content and terminology changes

| Current language | Recommended language | Reason |
|---|---|---|
| Ask the corpus | Ask BRSR Lens | “Corpus” is internal/research language |
| Refine the lens | Refine this view | Clear task language |
| Assurance | Assurance trends | Distinguishes market insight from filing readiness |
| Studio | Filing Studio | Makes purpose explicit |
| My benchmarks | Peer benchmarks | Clear before ownership has been established |
| Explore sector scorecards | Explore live insights | Broader and more outcome-oriented |
| A governed query out | Evidence-backed answer | Leads with user value; governance remains visible in details |
| Leading-sector completeness score | Highest sector completeness | Easier to parse |

Terms such as “substance,” “materiality,” “BRSR Core,” and “assurance” should remain because they are legitimate concepts, but receive concise inline definitions the first time they appear.

## 12. Homepage prototype scope

The local HTML prototype demonstrates:

- Simplified intent-led navigation
- Three entry paths
- A story-led, preconfigured insight
- Beginner/expert explanation toggle
- Contextual natural-language follow-up
- Prominent upload value proposition
- BRSR understanding meter and scenario quiz
- Clear separation between Assurance trends and Filing Studio

It is intentionally not a visual specification for every dashboard and does not connect to real APIs. Its purpose is to validate hierarchy, language, and journey before changing production components.

## 13. Delivery workstreams

These workstreams are implemented by the authoritative S18–S23 sequence in [`sessions/PHASE5_UX_REVAMP.md`](sessions/PHASE5_UX_REVAMP.md); the labels below describe product scope, not repository phase numbers.

### Workstream 1 — Reframe entry and navigation

- Replace the primary navigation and homepage hierarchy.
- Introduce intent cards and a guided insight preview.
- Rename Assurance, Studio, and Ask surfaces.
- Add contextual links to existing routes.
- Preserve all current routes and analytics while measuring the new entry points.

Success check: a first-time visitor can identify the Explore, Analyse, and File journeys in five seconds without BRSR-specific knowledge.

### Workstream 2 — Guided exploration

- Add curated question cards and preconfigured DSL views.
- Move complete filters into a progressive “Refine this view” control.
- Embed contextual Ask BRSR Lens entry and suggested follow-ups.
- Add plain-language result summaries and concept definitions.

Success check: users reach a meaningful insight before changing a filter; follow-up queries inherit the current cohort correctly.

### Workstream 3 — Analyse my BRSR

- Add the `/analyse` upload journey, privacy/consent copy, and progress states.
- Generate the at-a-glance report using existing extraction, score, lineage, and benchmark capabilities.
- Hand off cleanly to the peer benchmark and Filing Studio.

Success check: users understand the promised output before uploading and can trace every reported gap to evidence or an explicit absence of evidence.

### Workstream 4 — Learning layer

- Add Explain as I explore.
- Create the BRSR understanding model and scenario-question bank.
- Surface Learning Library content contextually.
- Add the `/learn` progress hub.

Success check: learning interactions increase exploration depth without lowering completion of analysis or filing tasks.

### Workstream 5 — Filing Studio entry improvements

- Add new/continue/import/analyse-report starting choices.
- Align terminology with the task language in this plan.
- Show the relationship between evidence gaps, readiness, formal assurance, and export.

Success check: users can explain what Studio will produce and what it will not do before creating a filing.

## 14. Measurement plan

Instrument the experience around user outcomes, not page views alone:

- Intent selection rate on home
- Time to first meaningful insight
- Curated question start and completion rate
- Follow-up query rate and successful-query rate
- “Show source” use rate
- Analyse-page visit → upload start → report completion funnel
- Analysis report → benchmark / Studio continuation
- Filing start → first section completion → evidence upload → readiness check → export
- Learn mode activation, dismissal, and return rate
- Knowledge-check completion and concept-help usage
- First-session return within 7 days

Segment results by anonymous/new, registered explorer, sustainability professional, and Studio organisation where consent and identification allow it.

## 15. UX acceptance criteria

- Every primary action is written as a user outcome.
- A beginner can explore at least one useful insight without understanding filters.
- An expert can reach full filters or the query workspace in one action.
- “Upload my BRSR” is visible in the first viewport on desktop and mobile.
- Upload privacy and output are clear before file selection.
- Natural-language queries inherit and display their current context.
- Assurance trends, filing readiness, and independent assurance are never presented as interchangeable.
- Learning mode is optional, dismissible, and does not block core work.
- Every score or recommendation provides methodology and evidence access where available.
- Existing shareable URLs, tier enforcement, suppression rules, and lineage behaviour remain intact.

## 16. Decisions to validate before implementation

Run five beginner and five sustainability-professional usability sessions against the prototype. Validate:

1. Whether “Analyse my BRSR” is understood as private report analysis rather than public submission.
2. Whether the three intent paths feel distinct without making the portal feel fragmented.
3. Whether “BRSR understanding” feels useful rather than patronising to experienced officers.
4. Whether experts can bypass explanations and reach dense controls quickly.
5. Whether “Assurance trends” and “Filing readiness” remove the current ambiguity.

Proceed with the full learning meter only if beginners value it and professional users can comfortably ignore it. The navigation and upload reframing do not depend on that result and should proceed independently.
