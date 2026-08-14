# DEPLOYMENT.md — BRSR Lens
### Single-node production on AWS EC2 · lighter twin of the VerityGrid deployment doctrine

## 1. Topology & sizing
| Node | Type | Runs | Notes |
|---|---|---|---|
| **app** | t3.large (2 vCPU/8 GB) beta → t3.xlarge at launch; 100 GB gp3; Elastic IP | nginx, frontend static, api, postgres(+pgvector), redis, worker (interactive queues), certbot | Memory split documented in compose.prod.yml; PG 2.5 g floor |
| **batch** (optional, default off) | c6i.xlarge, Terraform flag | worker (extract/parse/export queues) | Started for corpus runs & nightly reprocess; queue-routing config decides what runs where |
| S3 | — | `filings-raw`, `artifacts` (exports, page images), `backups` | Versioning + SSE + public-block |
External: LLM API (metered; SSM-held keys; per-org quotas in app), SES (lead routing + digests), Route53.

**Scaling story:** this serves launch traffic (≈300 concurrent public + tens of paid orgs). First moves when needed: t3.xlarge→m6i, split PG to its own node, CloudFront in front of static+public pages (cheap, likely the actual first move for a public content product), then ALB+second app node. All non-breaking.

## 2. Security groups & access
app-sg: 443/80 from world; 22 closed in normal ops (SSM Session Manager only; break-glass allowlist var). batch-sg: no inbound; egress only; reaches PG/Redis via private SG rule. Admin routes (`/admin/*`) additionally gated by role AND an IP-allowlist middleware (config) — public product, private cockpit.

## 3. Environments
dev = compose local (FakeLLM default) · sandbox = full Terraform stack in separate account/prefix for drills, load tests, infra rehearsal (destroy-tested) · prod. Infra changes rehearse in sandbox first. **LLM usage in sandbox uses capped keys** (separate provider key with hard budget — a runaway reprocess loop must not be able to spend the company's money; this is the LLM-era equivalent of a dev DB safety net).

## 4. Release flow, backups, DR
Identical doctrine to the sibling pack, restated short: CI builds → ECR (SBOM+vuln+secret gates) → operator-triggered `deploy.sh` (SSM) → SSM-rendered env → expand-only migrations → health-gated restart (<15 s blip, honest) → smoke → auto-rollback to `prev` + alert on failure. Backups: pgBackRest full weekly/diff daily/WAL PITR → S3 (30 d); artifacts/filings on versioned S3 (raw filings additionally lifecycle→IA at 90 d); page images recomputable (not backed up beyond S3 versioning). Restore drill scripted + executed in S19 and quarterly; targets RPO ≤ 15 min, RTO ≤ 3 h. Dead-man alert on missed backups.

## 5. The two human gates (mechanics live in code; signatures live with humans)
- **Legal gate:** source adapters ship default-OFF (S04); counsel reviews `SOURCES.md` + methodology/correction-SLA pages + Studio liability line; flipping an adapter flag in prod config is the signature's technical expression. Dated sign-off note in `docs/gates/legal.md` (S19).
- **Editorial gate:** publish gating policy (S06) + accuracy dashboards (`/admin/quality`) are the mechanism; the human confirms per-family accuracy ≥ targets before pin-to-public; families below target stay gated with confidence flags. Sign-off in `docs/gates/editorial.md` (S19). **No launch without both files existing.**

## 6. Operations cadence & cost guardrails
Monthly: infra bill review (alarm $300), **LLM spend review** (llm_usage dashboard; per-org quota tuning), corpus refresh planning (new FY filings arrive seasonally — the annual reprocess is a planned batch-node event with a budget, not a surprise). Quarterly: restore drill, dependency audit, score-drift review before any methodology version bump (public trust = no silent changes; methodology changelog is the public face of this discipline).

## 7. Launch checklist (S19 executes literally)
```
[ ] sandbox DR drill green ≤ 30 days before launch      [ ] authz route×role×tier matrix green on RC
[ ] load budgets met on prod-spec sandbox (numbers)      [ ] corpus coverage + publishability report accepted
[ ] editorial gate note committed                        [ ] legal gate note committed
[ ] methodology page live + matches scoring configs      [ ] correction channel tested end-to-end
[ ] lead routing tested to REAL BD inbox + webhook       [ ] pricing/plans config final; demo org purged
[ ] TLS grade A; DNS TTL lowered; CloudFront decision recorded
[ ] final backup + restore-verified                      [ ] on-call owner named; 48 h watch begins
[ ] v1.0.0 tagged; flagship-report data extracts delivered to analyst (business launch track)
```

## 8. Runbook skeleton (`ops/RUNBOOK.md`)
System map · start/stop (incl. batch-node economics) · deploy/rollback · incidents (api down / PG pressure / disk / queue stuck / LLM provider outage → FakeLLM degradation mode for NLQ ["temporarily unavailable" honesty banner] / cert expiry / runaway LLM spend → kill-switch env) · restore procedures · secret rotation · corpus-refresh procedure · gates & changelog discipline · escalation contacts.
