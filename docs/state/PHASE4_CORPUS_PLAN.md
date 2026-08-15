# Phase 4 corpus plan — NSE pilot to the 1,000-company run

Status: active preflight. Phase 3 remains complete; this work is an input to Phase 4 and does
not reopen or renumber the completed Phase 3 sessions.

## Sequence

| Order | Session | Corpus responsibility | Exit condition |
|---|---|---|---|
| 1 | S16 | Keep analytics/leads work unchanged. Stage the pilot artifacts in parallel; do not publish them. | Product work green; pilot provenance manifest exists. |
| 2 | S17 | Keep tiers, quotas, exports, and API work unchanged. Define which extracted families each tier can expose. | Entitlements remain independent of extraction. |
| 3 | S18 | Add the production ingestion foundations: NSE index adapter, batch/checkpoint queues, real embeddings, durable analysis-run cache, S3 raw/artifact stores, and spend telemetry. | A 25-filing dry run can resume without duplicate downloads or LLM calls. |
| 4 | S19A | Run the 25-filing calibration set through parse, retrieve, extract, validate, and human QA. | At least 400 hand-verified values; family accuracy and cost report signed. |
| 5 | S19B | Apply pilot fixes, freeze parser/prompt/schema versions, and rerun only invalidated work. | Publishable families meet the QA gate; cache reuse is demonstrated. |
| 6 | S19C | Run the governed 1,000-company corpus on the batch node, then complete hardening/UAT/release. | Existing S19 corpus, legal, editorial, security, load, and launch gates pass. |

The 25 reports are therefore a **Phase 4 preflight/calibration corpus**, not a new phase. Raw
files may be staged now, but live-LLM processing belongs to S19A after S18's cost, cache, and
batch controls are in place.

## Pilot corpus contract

- Source: official [NSE BRSR corporate-filings portal](https://www.nseindia.com/companies-listing/corporate-filings-bussiness-sustainabilitiy-reports).
- Reporting period: FY 2024–25 (`fyFrom=2024`, `fyTo=2025`).
- Cohort: 25 listed companies spanning banking, finance, technology, telecom, consumer,
  healthcare, autos, industrials, real estate, utilities, energy, mining, metals, and cement.
- Each logical filing has both the exchange PDF and XBRL. The pair shares one manifest row.
- Raw files live at `.data/corpus/nse-brsr/fy2024-25/` and are intentionally git-ignored.
- `corpus/manifests/nse_brsr_fy2024_25_pilot.csv` is the committed provenance record: source
  URLs, filing dates, local paths, byte counts, SHA-256 checksums, and acquisition time.
- The pilot downloader is resumable, validates file signatures, retries bounded failures, and
  defaults to 0.5 requests/second. A stale portal artifact fails closed rather than being
  silently accepted.

Reproduce or verify the acquisition with:

```bash
.venv/bin/python ops/corpus/acquire_nse_brsr_pilot.py
```

## Execution backlog

| ID | Session | Task | Acceptance |
|---|---|---|---|
| C01 | Preflight | Acquire the 25 PDF/XBRL pairs and commit their manifest. | 25 rows, 50 valid artifacts, unique checksums/provenance. |
| C02 | S18 | Replace URL templates with an NSE portal-index adapter and a reviewed source-policy record. Classify stale archive links separately from missing metadata and retry/fallback only through approved sources. | Cursor/date-window sync; ETag/checksum dedupe; fixture-backed tests incl. portal-row/404-artifact; source flag remains off by default. |
| C03 | S18 | Add batch orchestration by filing and stage, with checkpoints and dead-letter visibility. | Kill/restart resumes; no duplicate filing, extraction, or usage rows. |
| C04 | S18 | Persist `analysis_runs` keyed by source checksum, parser, taxonomy/schema, prompt, model, and retrieval configuration versions. | Identical key reuses results and incurs zero new model calls; changed input creates a new immutable run. |
| C05 | S18 | Replace hash embeddings in real runs with a configurable embedding provider while retaining the hash provider for offline tests. | Provider batching/retries/usage recorded; tenant-safe vector retrieval; offline suite remains network-free. |
| C06 | S18 | Implement hybrid section retrieval: heading/field lexicon + lexical score + vector score + adjacent-page windows. | Field-family retrieval recall benchmarked; the model never receives an entire long filing by default. |
| C07 | S18 | Route only low-confidence table pages to a vision-capable path; keep XBRL-first extraction deterministic. | Vision calls are explainable, metered, cached, and absent when XBRL supplies the fact. |
| C08 | S18 | Add canonical units, reporting-boundary tags, nil/not-applicable semantics, and cross-source conflict checks. | PDF/XBRL disagreements enter QA; values are never silently merged. |
| C09 | S19A | Import/parse all 25 pairs and produce a coverage/parse-quality report before any LLM call. | 25/25 parse outcomes recorded; failures classified; deterministic fields materialized. |
| C10 | S19A | Build the golden set, stratified by field family, XBRL/PDF, table/narrative, and confidence band. | At least 400 human-verified values with page/quote evidence. |
| C11 | S19A | Run live extraction in capped batches of five filings, review spend and accuracy after each checkpoint. | Token/cost/latency per filing and per accepted field reported; budget stop works. |
| C12 | S19B | Tune retrieval/prompts/validators from error classes, not individual-company patches. | Regression benchmark improves without reducing any passing family below its gate. |
| C13 | S19B | Freeze version set and demonstrate selective invalidation. | Second unchanged run makes zero model calls; a prompt-only change reruns only affected families. |
| C14 | S19C | Load the governed top-1,000 registry and execute acquisition/analysis in supervised batches. | Coverage and publishability meet the existing S19 targets or a variance is signed. |
| C15 | S19C | Complete legal/editorial gates, hardening, load/restore drills, UAT, and release. | Existing S19 definition of done is fully satisfied. |

## Extraction and persistence design

The source artifact and every derived result are durable. Redis remains an acceleration layer,
not the record of truth.

```text
NSE metadata + PDF/XBRL
        -> immutable raw object + SHA-256
        -> parse artifacts/pages/tables/embeddings
        -> retrieval bundle
        -> immutable analysis_run
        -> extracted field versions + evidence + validation
        -> human QA pin
        -> materialized public metrics
```

The analysis cache key must include:

```text
sha256(source checksums + parser version + taxonomy/schema version +
       prompt version + model/provider + retrieval configuration + validator version)
```

Consequences:

- An unchanged filing is downloaded/parsed/extracted once, then reused.
- A revised NSE filing creates a new lineage branch; it never overwrites reviewed evidence.
- Prompt, model, parser, or schema changes invalidate only the dependent stages.
- LLM response, structured output, evidence, token usage, latency, and error are stored on the
  analysis run. Redis may cache hot reads, but losing Redis cannot lose analysis.
- Publication still requires the existing confidence, family-accuracy, and human-pin gates.

## Live LLM configuration

Set these in the local `.env` only; never commit the secret:

```dotenv
LLM_PROVIDER=openai
LLM_API_KEY=your_real_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4.1-mini
LLM_NETWORK_ENABLED=true
```

`LLM_MODEL` now overrides the prompt's benchmark-baseline model at runtime. For a different
OpenAI-compatible provider, change provider label, base URL, model, and key together. Tests
must keep `LLM_PROVIDER=fake` and `LLM_NETWORK_ENABLED=false`.

The existing `EMBEDDING_MODEL=hash-embedding-v1` is only an offline deterministic embedding;
it does **not** call an embedding API. C05 must land before setting a real embedding model/key.
Until then, only the five LLM variables above should be changed for a live pilot.

## Guardrails before the API key is used

1. Parse and XBRL extraction must finish first; do not send deterministic facts to an LLM.
2. Run five filings per checkpoint with a hard token/cost ceiling.
3. Store the exact model, prompt version, request hash, usage, output, and evidence for every call.
4. Keep raw filings and model output private; only reviewed/pinned facts become public.
5. Do not start the 1,000-company run until C04–C08 and the 25-filing accuracy gate pass.
