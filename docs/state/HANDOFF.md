# HANDOFF — after S16 / Phase 4 (2026-08-15)

## Repo state: `main` · S16 complete · dev services up · migrations head `0007`

## Delivered

- `/api/admin/analytics` supplies ordered visit→signup→Pro and Studio→export funnels,
  feature use, deterministic embedding-clustered NLQ themes and sector interest; a weekly
  first-party digest is sent through the configured SMTP/SES path.
- `leads.yaml` drives rolling-window scores, occurrence caps, threshold/instant-route rules and
  legible signal timelines. Context-card email and optional CRM-neutral webhook routing enforce
  user opt-out plus one route per organisation per 14 days.
- `/deep-dive` captures a scoped company set, question, timeframe, budget band and contact email.
  `/api/admin/deepdives` enforces `new → scoped → quoted → delivered` ticket progression.
- `/admin/leads` records BD outcomes; `/api/admin/leads/quality` reports positive-outcome
  conversion by signal. `/admin/analytics` dogfoods the existing ECharts chart kit.
- Contextual expert CTAs now appear on company gap, Studio readiness and pricing surfaces.
  `/privacy` controls a browser/user opt-out; opting out deletes identified raw events.
- Raw events aggregate to `event_daily_aggregates` before deletion after 13 months. Hourly lead
  scoring, weekly digest and monthly retention jobs are registered with Celery beat.

## Contracts next session relies on

- Config: `leads.yaml` has `window_days`, `route_threshold`, `route_suppression_days` and signals
  with `weight`, `max_occurrences`, optional `event`/`property_contains`/`instant_route`.
- Webhook: `POST LEAD_WEBHOOK_URL`, canonical JSON `{version,event:"lead.ready",lead:{...}}`,
  `X-BRSRLens-Signature: sha256=<HMAC-SHA256(body, LEAD_WEBHOOK_SECRET)>`, three attempts.
- Routes: `POST /api/deepdives`; admin `/analytics`, `/leads`, `/leads/{id}/outcome`,
  `/leads/quality`, `/deepdives`, `/deepdives/{id}`; `PUT /api/privacy/preference`.
- Tables/columns: `event_daily_aggregates`; `users.analytics_opt_out`; lead outcome and route
  diagnostics; deep-dive company sets remain in `context_json.company_ids`.
- Schedule: lead score hourly; digest every 7 days; retention every 31 days. Raw retention is
  configured by `ANALYTICS_RETENTION_MONTHS` (default 13).

## Sharp edges

- Routing is deliberately inert until `LEAD_ROUTING_ENABLED=true`; webhook is optional and SMTP
  uses the existing MailHog/SES-compatible path.
- NLQ themes use deterministic hash embeddings for offline CI; labels are market-research aids,
  not user profiles.
- The browser host bridge could not initialize; S16 visual/keyboard inspection is in BACKLOG.

## Env/secrets added

- `ANALYTICS_RETENTION_MONTHS`, `ANALYTICS_DIGEST_RECIPIENTS`, `LEAD_ROUTING_ENABLED`,
  `LEAD_RECIPIENT_EMAIL`, `LEAD_WEBHOOK_URL`, `LEAD_WEBHOOK_SECRET`

## Next: S17 — tier enforcement completion, billing-lite and export polish

Start from migration `0007`; reuse the registered `plan_changed_to_pro` funnel event and route
pricing/contact actions through the explicit S16 conversion surfaces.
