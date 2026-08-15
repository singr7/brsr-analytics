# PHASE 4 — Engagement & Commercial Foundations (S16–S17)

---
## S16 — Product analytics surfaces, lead engine, deep-dive workflow
**GOAL:** Turn the event stream (live since S03) into: an internal analytics view, a legible lead engine routing to Panacea Bioedge, and the productised deep-dive request flow.

**READ:** HANDOFF, `events` model + events.yaml, 00_ARCHITECTURE §4, mailhog wiring.

**TASKS**
1. Internal analytics (`/admin/analytics`, ECharts on the events table — first-party dogfooding): funnels (visit→signup→pro, studio start→export), NLQ question themes (clustered via embeddings — what the market asks is market research), feature usage, sector-interest heat, weekly digest email to the team (SES/mailhog).
2. **Lead engine** (`services/leads.py` + `leads.yaml` weights per architecture §4): scoring job over rolling event windows → `leads` rows with signals timeline; routing: SES **context-card email** to Bioedge BD (who/org/company-viewed/signals/suggested opening line — template carefully: it should read like a thoughtful colleague's note, not tracker output) + webhook POST (HMAC-signed, retry, CRM-agnostic JSON) behind config; suppression rules (one route per org per 14 days; opt-out honored absolutely).
3. Conversion surfaces (frontend): clearly-labeled, contextual — gap panel footer ("Close these gaps with an expert — talk to Panacea Bioedge"), Studio gap-report CTA, pricing-page contact, **"Request an expert deep-dive"** page: scoped form (question, company set, timeframe, budget band) → `deepdive_requests` → ticketed admin workflow (statuses: new→scoped→quoted→delivered) → instant lead route. No modal ambushes, no dark patterns — the brand is trust.
4. Lead quality feedback loop: BD outcome field on leads (admin) → weight-tuning report (`/admin/leads/quality`: conversion by signal — the data to argue about weights with, not vibes).
5. Privacy completion: events retention policy (raw 13 months → aggregates), opt-out cookie honored in beacon + server emits, privacy page copy hooks.

**SELF-CHECK:** scoring goldens (constructed event timelines → expected scores/routes) · suppression + opt-out tests · webhook signature/retry test · context-card snapshot (read it aloud — would BD thank you?) · funnel queries correct on seeded events · verify green.
**COMMITS:** `feat(leads): scoring + routing + context cards [S16]`, `feat(engage): deep-dive workflow + surfaces [S16]`, `feat(admin): analytics + lead quality [S16]`, close.
**HANDOFF:** leads.yaml semantics, webhook contract, deep-dive states, retention jobs schedule.

---
## S17 — Tier enforcement completion, billing-lite, exports polish
**GOAL:** Monetisation mechanics without a payment gateway: licence-managed plans, quota enforcement everywhere, and the paid artifacts polished.

**READ:** HANDOFF, plans/tier matrix (S03), quota scaffolds (S03/S11/S14).

**TASKS**
1. Billing-lite: admin plan management (assign tier + seats + term to org), licence-expiry behavior (grace → read-only), invoice-request flow (SES to ops with plan sheet; Razorpay adapter stubbed behind flag per non-goals), plan-change events.
2. Quota unification: one `services/quotas.py` (NLQ/day, Studio tokens/month, seats, export counts) with headroom warnings surfaced in-product at 80% (a nudge, not a wall — and an upsell event).
3. Paid-artifact polish: board-PDF theming pass (S10), Studio draft typography pass (S15), Research-tier dataset export (`/api/export/dataset` — documented CSV/parquet of public-tier aggregates + licence terms embedded in file header; full-corpus licence = manual fulfilment note).
4. Public API keys (Research tier): scoped key issue/revoke, per-key rate limits, `/api/v1/query` (the S08 DSL, read-only, public-measure subset) + OpenAPI docs page — the academic/investor hook with near-zero extra surface (the semantic layer pays off again).
5. Pricing page: tier comparison rendered from the same plans config (single source of truth), FAQ, contact-sales.

**SELF-CHECK:** expiry/grace state machine tests · quota matrix parametrised test (every quota × tier) · API-key auth + scope tests · dataset export golden w/ licence header · pricing renders from config (change config → page changes, test) · verify green.
**COMMITS:** `feat(billing): plans + licences + invoice flow [S17]`, `feat(quota): unified enforcement [S17]`, `feat(api): keyed public query API [S17]`, close.
**HANDOFF:** plan config location, quota keys, API-key contract, manual fulfilment runbook notes.

---

Infrastructure, corpus, hardening, and launch continue in `PHASE6_PRODUCTION.md` as S24–S25 after the S18–S23 UX phase.
