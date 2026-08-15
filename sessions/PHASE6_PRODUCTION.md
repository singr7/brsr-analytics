# PHASE 6 — Infrastructure, Corpus & Launch (S24–S25)

*The production estate and governed launch. Renumbered from S18–S19 so the intent-led UX is implemented and assured before production UAT.*

---

## S24 — AWS infrastructure & deployment

**GOAL:** Terraform estate + hardened single-node deploy per DEPLOYMENT.md; first production deploy executed.

**READ:** HANDOFF, 00_ARCHITECTURE §7, DEPLOYMENT.md (full), S23 final route/smoke inventory.

**TASKS**
1. Terraform (state S3+lock): VPC (single public subnet), EC2 app node (t3.large; `instance_type` var for launch bump; 100 GB gp3), optional batch node (flag, default off, same AMI/profile), Elastic IP, S3 buckets (`filings-raw`, `artifacts`, `backups`; versioning+SSE+public-block), IAM least-privilege roles (app: buckets+SSM `/brsrlens/*`+SES; deployer for CI), ECR repos, Route53, SSM Session Manager, CloudWatch alarms (status, CPU, disk, budget $300) → SNS email.
2. cloud-init: docker+compose, ECR helper, `/opt/brsrlens/{env,compose,data}`, systemd unit, unattended security upgrades; compose.prod.yml with memory limits for the t3.large split (PG 2.5g / api 1.5g / worker 2g / redis+nginx 0.5g — and the documented rule: **extraction batch runs happen on the batch node or off-hours**, enforced by worker queue routing config).
3. CI/CD: build+push on main (multi-stage, non-root, SBOM+grype gate, trufflehog), operator-triggered `deploy.sh` via SSM: SSM-rendered `.env`, pull, `alembic upgrade` (expand-only), health-gated restart, `ops/smoke.sh` (healthz, login, guided Explore query, analysis contract fixture, one lineage fetch), auto-rollback to `prev` on smoke failure + alert.
4. TLS: nginx + certbot, HSTS, security headers, gzip/brotli, static caching, upload caps (analysis and Studio 100 MB), rate-limit zones (public API, NLQ, analysis upload/status).
5. Execute: sandbox apply → prod apply → first deploy → seed prod admin → smoke green over HTTPS on the real domain.
6. Corpus-run foundations required before S25: NSE portal-index adapter + governed cursors, resumable stage/batch queues, real embedding-provider adapter (hash provider retained for offline tests), hybrid section retrieval, and immutable `analysis_runs` keyed by source/parser/schema/prompt/model/retrieval versions. Identical reruns must reuse stored analysis with zero LLM calls; Redis is only a hot-read cache. Follow `docs/state/PHASE4_CORPUS_PLAN.md` C02–C08.

**SELF-CHECK:** fresh sandbox apply < 15 min; plan-after-apply empty; tfsec clean/waivered · forced-bad-image deploy auto-rolls back with alert received · SSL grade A · SSM-only access verified (no SSH ingress in normal ops) · private analysis objects blocked from public access · verify green.
**COMMITS:** `infra(tf): estate [S24]`, `infra(boot+deploy): cloudinit + cd + rollback [S24]`, `infra(tls): nginx hardening [S24]`, close.
**HANDOFF:** outputs inventory, deploy runbook pointer, measured deploy blip, parameter inventory, final smoke route list.

---

## S25 — Corpus run, hardening, gates, and launch

**GOAL:** The real 1,000-company corpus built under supervision; security/load hardening; editorial, legal, and UX gates signed; launch.

**READ:** HANDOFF, QA_PLAN §6–7, DEPLOYMENT §5–6, BACKLOG triage, `docs/gates/ux.md`.

**TASKS**
0. **25-filing corpus preflight (S25A):** use the checksummed NSE FY 2024–25 PDF+XBRL pairs staged under `docs/state/PHASE4_CORPUS_PLAN.md` → deterministic parse/XBRL extraction first → live-LLM batches of five only for unresolved fields → ≥400 hand-verified values → accuracy/cost/error report → tune and freeze parser/prompt/schema/retrieval versions. Prove an unchanged rerun makes zero new LLM calls before scaling.
1. **Corpus production run (S25B/C, with the human):** after the preflight gate, legally-enabled adapters on (post legal gate) → acquisition sweep → coverage report → parse+extract in batches (batch node; spend meter watched; checkpoint after each batch) → QA sampling to protocol (QA_PLAN §4: per-family sample sizes) → pin what passes; publish-coverage report (what % of fields public at launch, by family — honesty artifact for the methodology page).
2. Security hardening: route×role×tier authz matrix test (every route, parametrised), org/tenant isolation re-sweep including Studio and private-analysis retrieval/storage paths, upload handling (content-type, AV-scan via clamav container, size), SSRF sweep on URL fields, dependency audits, `SECURITY.md`.
3. Load & soak: k6 — public browse 300 concurrent + 30 NLQ/min + 5 analysis uploads/hour + 5 Studio orgs active, 2 h soak on prod-spec sandbox; budgets: dashboards p95<400 ms, NLQ p95<6 s, stable upload/status queues, no memory creep; capacity statement recorded.
4. Backups/DR execution (per DEPLOYMENT §4): pgBackRest full+diff+WAL to S3, restore drill executed with row-count + pin-integrity + private-report metadata assertions, artifact/S3 lifecycle checks, dead-man backup alert tested; RTO/RPO recorded.
5. **Gates signed (human):** Editorial — accuracy and publication thresholds; Legal — sources, methodology, privacy/retention, analysis promise, and Studio liability; UX — S23 comprehension/accessibility evidence still matches deployed build. Commit dated notes in `docs/gates/`.
6. UAT (QA_PLAN §6, two humans) → P0/P1 fixed; launch checklist executed; `v1.0.0`; 48 h watch active. Include new Home→Explore, contextual Ask, private Analyse→benchmark/Studio, learning preference, and expert-bypass journeys in addition to existing trust/Studio/engagement/ops flows.

**SELF-CHECK:** corpus coverage ≥90% with ≥80% Core-field publishability (or signed variance) · authz/isolation matrix green · load budgets met · restore drill green · editorial/legal/UX gates committed · UAT P0=P1=0 · v1.0.0 tagged.
**COMMITS:** `chore(corpus): production run artifacts and coverage report [S25]`, `fix(sec): hardening findings [S25]`, `chore(release): v1.0.0 launch [S25]`, close.
**HANDOFF (final → OPERATIONS edition):** system state, corpus stats, capacity statement, route/funnel baselines, enabled UX flags, alert routes, drill cadence, spend dashboard pointers, top-10 BACKLOG for v1.1.
