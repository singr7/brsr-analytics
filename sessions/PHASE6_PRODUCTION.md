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

## S24B — Object lifecycle: page-image reclamation

**GOAL:** Give the object store a delete path and reclaim superseded parse artifacts, so the 1,000-filing corpus run does not accumulate orphaned page images. Must land before S25B.

**READ:** HANDOFF, `api/app/services/storage.py`, `worker/parse/service.py:129-167`, `infra/terraform/storage.tf` (lifecycle rules), `infra/terraform/iam.tf` (`ReadWriteBuckets`).

**WHY (analysis, 2026-08-17 — do not re-derive):**
`parse_filing` renders every located BRSR page to a 150-DPI PNG and PUTs it under
`pages/{filing_id}/v{parse_version}/`. On re-parse it deletes the `FilingPage` rows but the
previous version's PNGs stay in S3 forever: `ObjectStore` exposes only `put` and `get`, with no
delete anywhere in the codebase. At 1,000 filings and ~60 BRSR pages each that is ~60,000 objects
and ~18 GB per parse version, permanently orphaned on every sweep — roughly $0.45/month added per
sweep and never reclaimed, plus $0.30 in PUTs and $0.60 in lifecycle transitions per sweep.

Re-parse is the trigger, and it is not rare. Extraction does **not** read the raw object
(`run_extraction` reads `FilingPage.text` from Postgres), so prompt tuning costs nothing here. What
forces a re-parse: `locate_brsr_sections` changes (it sets the section bounds, so a locator miss
means those filings must be re-parsed — subsets weekly during pipeline work, full corpus 2–6 times
this phase), `FieldDef.xbrl_concept` mapping changes for XBRL filings, `detect_table_regions`
tuning, any DPI change, and DR when Postgres is restored older than the S3 objects.

**Decided against:** a local read cache for raw filings. At 1,000 filings (~8 GB) a full-corpus
re-parse reads ~$0.08 of S3 — GETs are $0.0004/1,000 and in-region transfer to EC2 is free — so six
sweeps a year is under $0.50, while caching 8 GB on gp3 costs ~$8.75/year. The cache would cost
more than the reads it eliminates, and the loop it would have accelerated does not touch S3.

**TASKS**
1. Extend the `ObjectStore` protocol with `delete(uri)` and `delete_prefix(prefix)`; implement on `LocalObjectStore` (same root-escape guard as `put`/`get`) and `S3ObjectStore` (SigV4 `DELETE`, plus `ListObjectsV2` paging for prefix deletes, batched via `POST ?delete` where it pays).
2. Handle versioning honestly. The filings bucket has versioning enabled, so a plain `DeleteObject` writes a delete marker and the bytes stay billed until `noncurrent_version_expiration` (currently 90 days). Either delete by `versionId` — which needs `s3:DeleteObjectVersion` added to the `ReadWriteBuckets` statement, it is **not** granted today — or add a `pages/`-prefixed lifecycle rule with a short noncurrent expiration and expired-delete-marker cleanup. Record which and why.
3. Call it on supersede: after `parse_filing` commits the new `parse_version`, delete the previous `pages/{filing_id}/v{n}/` prefix. Delete after commit, never before — a failed re-parse must not destroy the artifacts still referenced by live `FilingPage` rows.
4. One-shot reclamation for what has already accumulated: an operator command in `ops/bin/brsrlens-prod` that lists `pages/` prefixes, diffs against the `parse_version` each `FilingPage` actually references, reports the reclaimable bytes, and deletes only on `--apply`. Dry-run by default.
5. Split the lifecycle rules. `raw-filings-to-ia` uses `filter {}`, so it sweeps the page PNGs too, and STANDARD_IA bills a 128 KB minimum per object — most pages are smaller. Scope the IA transition to `raw/` and give `pages/` its own rule. Note the IA 30-day minimum-duration charge when deleting transitioned objects early.
6. Tests: prefix delete removes only the target version; root-escape rejection on both stores; supersede leaves the current version's images intact and reachable via `trust.py`/`quality.py` image URLs; a failed re-parse deletes nothing; reclamation dry-run reports without deleting.

**SELF-CHECK:** re-parse of a fixture filing leaves exactly one `pages/` version in the store · no orphan bytes after two consecutive re-parses (measure, don't assume) · delete-by-version or lifecycle path verified against a versioned bucket, with reclamation confirmed rather than delete-markered · reclamation command dry-run matches the DB-referenced set · `s3_image` URLs still resolve for every live page after reclamation · IAM change applied with an empty plan after apply · `make verify` green.
**COMMITS:** `feat(storage): delete path for superseded parse artifacts [S24B]`, `infra(tf): page-image lifecycle and version-delete permission [S24B]`, `infra(ops): orphan reclamation command [S24B]`, close.
**HANDOFF:** measured bytes reclaimed, per-sweep storage growth after the change, versioning decision and its reclamation lag, remaining prefixes with no delete path.

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
