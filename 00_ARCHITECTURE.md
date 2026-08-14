# 00 — Architecture & Technical Decisions (BRSR Lens)

## 1. System overview
```
                    ┌──────────────────── EC2 "app" (t3.large → xlarge at launch) ───────────────────┐
 Browser ─ HTTPS ─► nginx ─► frontend (React static, public + gated areas)                           │
                    │    └──► api (FastAPI)                                                           │
                    │           ├── Postgres 16 + pgvector (EVERYTHING: relational, vectors, FTS,     │
                    │           │    analytics events)                                                │
                    │           └── Redis 7 (queue, cache, rate limits)                               │
                    │    worker (Celery): acquisition, parsing, LLM extraction, scoring, exports      │
                    └───────────────────────────────┬─────────────────────────────────────────────────┘
                                                    │
              S3: raw filings (PDF/XBRL), page images, exports, backups        LLM API (external, §5)
```
**One database on purpose.** ~1,000 companies × ~2,000 fields × a few years ≈ low-millions of rows — trivially Postgres-scale. Postgres FTS covers lexical search over filing text; **pgvector** covers semantic search and NLQ retrieval; a `metrics` star-schema covers analytics. No Elasticsearch, no warehouse, no second system to operate, back up, or explain in diligence. Revisit only if corpus grows 50× or query latency p95 exceeds budgets (§7).

## 2. Stack (pinned; agent must not substitute)
| Layer | Choice | Rationale |
|---|---|---|
| API | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic | Same conventions as sibling repo; agents fluent |
| DB | Postgres 16 + pgvector + FTS | §1; one system of record incl. embeddings and product-analytics events |
| Jobs | Celery 5 + Redis | Parsing/extraction/exports are batch; boring wins |
| Parsing | `lxml`/`arelle`-assisted XBRL reading; `pymupdf` (fitz) for PDF text+layout; page images for LLM vision fallback | BRSR arrives as exchange XBRL and/or PDF sections of annual reports — both paths first-class |
| LLM usage | Provider-agnostic client (`services/llm.py`), models configured per task; **prompts as versioned YAML + fixture responses** | Extraction, NLQ, doc-to-draft; offline-testable by doctrine |
| Frontend | React 18 + Vite + TS + Tailwind + **ECharts** + TanStack Query/Table | Public product needs polished custom viz — not Kibana; ECharts: rich, themable, no licence friction |
| PDF/Word export | WeasyPrint (HTML→PDF), `python-docx` | Board drafts + gap reports |
| XBRL export | Template-driven instance generation against the exchange BRSR taxonomy (versioned in `taxonomy/`) + arelle validation pass | The Filing Studio's compliance heart (§6) |
| Product analytics | **First-party**: `events` table + tiny JS beacon | §4 — no third-party trackers on a trust product |
| Containers/IaC/CI | Docker+compose, Terraform+cloud-init, GitHub Actions → ECR → SSH/SSM deploy | Identical model to sibling repo |

## 3. Data model spine (S02 owns DDL; invariants here)
- **Corpus:** `companies(id, cin, name, ticker, exchange, sector, industry, mcap_band)` · `filings(id, company_id, fy, source enum[xbrl,pdf,manual], s3_raw, status, acquired_at)` · `filing_pages(filing_id, page_no, text, s3_image)` · `extracted_fields(id, filing_id, field_key, value_raw, value_num?, unit?, confidence, method enum[xbrl,llm,human], source_page, source_span, qa_status enum[unreviewed,sampled_ok,corrected], version)` — **every published number traces to (filing, page, span); this lineage is the brand** · `field_defs(field_key, principle, section, label, dtype, unit_family, core_kpi bool)` — the BRSR schema-as-data, versioned (format changes are data migrations, not code rewrites).
- **Analytics:** `metrics(company_id, fy, metric_key, value, percentile_sector, percentile_all, yoy_delta)` (materialised by S07) · `scores(company_id, fy, score_key[completeness,substance,assurance_readiness…], value, components_json, method_version)`.
- **Studio:** `studio_orgs`, `studio_filings(org_id, fy, status draft→review→final)`, `studio_answers(filing, field_key, value, evidence_doc?, confidence, author enum[user,ai], review_status)`, `studio_docs(org, kind, s3, parsed_json)`.
- **Engagement:** `events(anon_id?, user_id?, session_id, name, props_json, ts)` (partitioned monthly) · `leads(id, user/org, score, signals_json, status, routed_at)` · `deepdive_requests(...)`.
- **Access:** `users, orgs, memberships, plans(tier explore|pro|studio|research), api_keys`.
- Extraction is **append-only versioned**: corrections create new versions; public views pin to latest QA-passed version. Nothing published is ever silently mutated.

## 4. Product-analytics & lead doctrine (first-party, honest)
- Self-hosted beacon → `events` table. No Google Analytics/third-party pixels: this portal preaches data discipline; it practices it. Cookie banner minimal (first-party analytics disclosed); anonymous IDs until signup, merged on registration.
- **Lead scoring is rule-based and legible** (`services/leads.py`, weights in `leads.yaml`): e.g., viewed own-company gap panel ×3 in 7 days (+30), generated Studio gap report (+40), NLQ mentioning "assurance"/"BRSR Core deadline" (+15), pricing page (+10), deep-dive request (+50 → instant route). Score ≥ threshold → lead created → SES email to Bioedge BD with a **context card** (who, org, signals timeline, suggested opening) + optional webhook (CRM-ready). No dark patterns: every conversion surface is a clearly-labeled "Talk to Panacea Bioedge" / "Request an expert deep-dive" action.
- Deep-dive requests are productised: request form (scope, company set, question) → ticketed workflow → delivered as paid engagement; the request itself is the highest-intent lead signal.

## 5. LLM usage doctrine (three tasks, one discipline)
| Task | Pattern | Guardrail |
|---|---|---|
| Field extraction (S06) | Per-section prompts over XBRL-missed/PDF-only fields; JSON-schema-constrained output; page-image vision fallback for tables | Confidence per field; below `publish_threshold` (policy) → never public without human QA; extraction benchmark gate (QA_PLAN §4) |
| NLQ (S11) | LLM translates question → **semantic-layer DSL** (S08), never raw SQL; the executed query + filters are shown to the user ("here's what I ran") | DSL whitelist = no injection surface; unanswerable → honest refusal + suggested filters; every NLQ logged as event (product-insight goldmine) |
| Doc-to-draft (S14) | Company docs parsed → candidate answers mapped to `field_defs` with confidence + evidence pointer; user reviews everything | AI never finalises a filing answer; review status tracked per field; export blocked while required fields are `ai_unreviewed` |
Prompts in `prompts/*.yaml` (versioned, with model + params); fixture responses committed for offline tests; nightly live-accuracy runs report drift.

## 6. Filing Studio format doctrine
The prescribed BRSR structure (Sections A/B/C, nine principles, Essential+Leadership indicators, BRSR Core KPIs) is encoded **as data** in `field_defs` + `form_schema.yaml` (order, conditionality, validations, XBRL concept mapping), versioned per SEBI/exchange taxonomy release. When the format changes (it will), the fix is a schema-data update + taxonomy drop-in, validated by arelle against the new taxonomy — sessions build the engine, not a hard-coded form. Validation layers: dtype/unit → cross-field consistency (e.g., totals vs breakdowns, YoY sanity) → completeness per Core → arelle taxonomy validation on export. The **gap report** (assurance-readiness) is generated from the same validation output — the compliance tool and the lead magnet are one artifact.

## 7. AWS managed vs self-managed (lighter twin of the sibling decision table)
S3/SES/SSM/ECR/Route53 managed (same rationale as sibling repo §3); Postgres/Redis/nginx+certbot self-managed on one EC2 (t3.large dev/beta → t3.xlarge at launch, 100 GB gp3); worker runs on the same instance (extraction batches are overnight jobs; a second stopped "batch" instance is a Terraform flag, off by default). No ALB/RDS/OpenSearch — revisit triggers: >3k concurrent users, DB > 100 GB, or team > 1 ops owner. Indicative cost: **$90–140/mo** + LLM API spend (budget: extraction of 1,000 filings ≈ one-off $1.5–4K depending on PDF share and model mix; NLQ/Studio inference metered per plan). Budget alarm at $300/mo infra + monthly LLM-spend review; per-org token quotas enforced in `services/llm.py`.

## 8. Performance & quality budgets (tested in S19)
Public dashboard p95 < 400 ms (metrics are pre-materialised; charts hit `metrics/scores`, never raw fields) · NLQ end-to-end p95 < 6 s · extraction pipeline: full 1,000-filing reprocess < 24 h on batch instance · published-field extraction accuracy ≥ 98% on the QA benchmark set (QA_PLAN §4) — below that, the field family stays Tier-B-gated with confidence flags, not public.

## 9. Non-goals (MVP)
Payment gateway (invoicing + licence keys first; Razorpay stub behind a flag), mobile apps, real-time collaboration in Studio (single-editor + comments only), multi-language filings (English first; Hindi extraction BACKLOG), auto-submission to exchanges (we produce validated files; the company files them — liability line stated in-product).
