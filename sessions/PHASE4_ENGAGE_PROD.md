# PHASE 4 — Engagement & Production (S16–S19)

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
## S18 — AWS infrastructure & deployment
**GOAL:** Terraform estate + hardened single-node deploy per DEPLOYMENT.md; first production deploy executed.

**READ:** HANDOFF, 00_ARCHITECTURE §7, DEPLOYMENT.md (full).

**TASKS**
1. Terraform (state S3+lock): VPC (single public subnet), EC2 app node (t3.large; `instance_type` var for launch bump; 100 GB gp3), optional batch node (flag, default off, same AMI/profile), Elastic IP, S3 buckets (`filings-raw`, `artifacts`, `backups`; versioning+SSE+public-block), IAM least-privilege roles (app: buckets+SSM `/brsrlens/*`+SES; deployer for CI), ECR repos, Route53, SSM Session Manager, CloudWatch alarms (status, CPU, disk, budget $300) → SNS email.
2. cloud-init: docker+compose, ECR helper, `/opt/brsrlens/{env,compose,data}`, systemd unit, unattended security upgrades; compose.prod.yml with memory limits for the t3.large split (PG 2.5g / api 1.5g / worker 2g / redis+nginx 0.5g — and the documented rule: **extraction batch runs happen on the batch node or off-hours**, enforced by worker queue routing config).
3. CI/CD: build+push on main (multi-stage, non-root, SBOM+grype gate, trufflehog), operator-triggered `deploy.sh` via SSM: SSM-rendered `.env`, pull, `alembic upgrade` (expand-only), health-gated restart, `ops/smoke.sh` (healthz, login, /query fixture, one lineage fetch), auto-rollback to `prev` on smoke failure + alert.
4. TLS: nginx + certbot, HSTS, security headers, gzip/broti, static caching, upload caps (Studio 100 MB), rate-limit zones (public API, NLQ).
5. Execute: sandbox apply → prod apply → first deploy → seed prod admin → smoke green over HTTPS on the real domain.

**SELF-CHECK:** fresh sandbox apply < 15 min; plan-after-apply empty; tfsec clean/waivered · forced-bad-image deploy auto-rolls back with alert received · SSL grade A · SSM-only access verified (no SSH ingress in normal ops) · verify green.
**COMMITS:** `infra(tf): estate [S18]`, `infra(boot+deploy): cloudinit + cd + rollback [S18]`, `infra(tls): nginx hardening [S18]`, close.
**HANDOFF:** outputs inventory, deploy runbook pointer, measured deploy blip, param inventory.

---
## S19 — Corpus run, hardening, gates, launch
**GOAL:** The real 1,000-company corpus built under supervision; security/load hardening; the two human gates signed; launch.

**READ:** HANDOFF, QA_PLAN §6 (UAT) + §7 (gates), DEPLOYMENT §5–6, BACKLOG triage.

**TASKS**
1. **Corpus production run** (with the human): legally-enabled adapters on (post legal gate) → acquisition sweep → coverage report → parse+extract in batches (batch node; spend meter watched; checkpoint after each batch) → QA sampling to protocol (QA_PLAN §4: per-family sample sizes) → pin what passes; publish-coverage report (what % of fields public at launch, by family — honesty artifact for the methodology page).
2. Security hardening: route×role×tier authz matrix test (every route, parametrised — the flagship security test), org/tenant isolation re-sweep incl. Studio corpus retrieval paths, upload handling (content-type, AV-scan via clamav container, size), SSRF sweep on any URL fields, dependency audits, `SECURITY.md`.
3. Load & soak: k6 — public browse 300 concurrent + 30 NLQ/min + 5 Studio orgs active, 2 h soak on prod-spec sandbox; budgets: dashboards p95<400 ms, NLQ p95<6 s, no memory creep; capacity statement recorded.
4. Backups/DR execution (per DEPLOYMENT §4): pgBackRest full+diff+WAL to S3, restore drill executed with row-count + pin-integrity assertions, artifact/S3 lifecycle checks, dead-man backup alert tested; RTO/RPO recorded.
5. **Gates signed (human):** *Editorial* — `/admin/quality` accuracy ≥ targets per published family; below-target families confirmed gated; methodology page matches reality. *Legal* — SOURCES.md counsel-reviewed; methodology + correction-SLA page reviewed; Studio liability line reviewed. Sign-offs committed as dated notes in `docs/gates/`.
6. UAT (QA_PLAN §6 script, 2 humans) → P0/P1 fixed; launch checklist (DEPLOYMENT §7) executed line-by-line; `v1.0.0`; 48 h watch protocol active; the T-6-weeks launch-play items (strategy doc §6) are the *business* track running parallel — engineering's contribution: the flagship-report data extracts delivered to the analyst.

**SELF-CHECK:** corpus coverage ≥ 90% of registry with ≥ 80% Core-field publishability (or consciously-documented variance) · authz matrix green · load budgets met (numbers) · restore drill green (RTO recorded) · both gate notes committed · UAT P0=P1=0 · v1.0.0 tagged.
**COMMITS:** `chore(corpus): production run artifacts + coverage report [S19]`, `fix(sec): hardening findings [S19]`, `chore(release): v1.0.0 launch [S19]`, close.
**HANDOFF (final → OPERATIONS edition):** system state, corpus stats, capacity statement, alert routes, drill cadence, spend dashboard pointers, top-10 BACKLOG for v1.1 (candidates: Hindi extraction, Razorpay, real-time Studio collab, fusion-workload API for VerityGrid).
