# HANDOFF — after S17 / Phase 4 (2026-08-15)

## Repo state: `main` · S17 complete · dev services up · migrations head `0008`

## Delivered

- `plans.yaml` is the source for tier copy, default seats and NLQ/Studio/export/API quotas; both
  `/api/plans` and `/pricing` render it. `/billing` sends an owner-authorised manual invoice brief.
- Platform admins assign tier, seats, start, expiry and grace through
  `PUT /api/admin/orgs/{org_id}/licence`; expiry moves through active → grace → read-only, preserving
  reads while blocking Studio writes, exports, invitations and key issuance.
- `services/quotas.py` enforces NLQ/day, Studio tokens/month, seats, exports/month and Research API
  requests/minute; 80% headroom is surfaced and emits one registered warning per user/day.
- Research owners issue/list/revoke one-time-secret keys at `/api/research/keys`. `X-API-Key`
  authenticates `/api/v1/query` and `/api/export/dataset?format=csv|parquet` with explicit scopes.
- Research queries expose only completeness, substance and assurance-readiness. Dataset exports
  suppress cohorts below the catalog minimum and embed licence/methodology metadata.
- Peer-board PDF and Studio PDF/DOCX typography are polished; full-corpus delivery is documented in
  `ops/RESEARCH_FULFILMENT.md` and remains deliberately manual.

## Contracts next session relies on

- Plan config: `plans.yaml`; quota keys `nlq_per_day`, `studio_tokens_per_month`,
  `exports_per_month`, `api_queries_per_minute`; default seat counts live beside them.
- Licence columns: `orgs.seat_limit`, `licence_starts_at`, `licence_expires_at`,
  `licence_grace_until`; state is computed by `services.plans.licence_state`.
- API keys: `brsrl_…` secret shown once, SHA-256 at rest, scopes `query:read`/`dataset:read`,
  `X-API-Key`, 60 requests/minute; revoked/read-only keys fail closed.
- Dataset formats: CSV comment header or Parquet schema metadata; both carry licence, methodology
  and manual full-corpus notes. Public API docs are at `/docs`.
- Invoice requests are stored in `invoice_requests` and emailed through SMTP; enabling
  `RAZORPAY_ENABLED` returns 503 without charging until a real adapter is implemented.

## Sharp edges

- Full-corpus licensing cannot use self-service export; follow `ops/RESEARCH_FULFILMENT.md`.
- The Research dataset intentionally contains sector aggregates only and applies cohort suppression.
- PyArrow adds ~33 MB to local downloads/~42 MB in the Linux image; allow for this in S18 sizing.
- The in-app browser could not initialize; S17 pricing/billing visual/keyboard inspection is in
  BACKLOG. Live API/OpenAPI smoke and component tests passed.

## Env/secrets added

- `BILLING_OPS_EMAIL`, `RAZORPAY_ENABLED`

## Next: S18 — AWS infrastructure & deployment

Start from migration `0008`; copy `plans.yaml` into production images and include PyArrow in image
size/memory checks. Terraform, cloud-init, hardened Compose, CI/CD rollback, TLS and corpus-run
foundations are next; production apply/domain/SES actions still require operator-owned credentials.
