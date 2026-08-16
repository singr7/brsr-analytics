# 01 — Conventions & Session Protocol (BRSR Lens)
### Read at the start of EVERY session. Protocol is identical to the VerityGrid pack; deltas are marked ◆.

## 1. Repo layout
```
brsrlens/
├── api/app/{core,models,schemas,routers,services}/   # FastAPI; routers thin, services thick
├── api/alembic/  api/tests/
├── worker/{acquire,parse,extract,score,studio,exportgen}/  worker/tests/
├── frontend/                      # React+Vite+TS+Tailwind+ECharts
├── prompts/                       # ◆ versioned LLM prompt YAMLs + fixtures/ responses
├── taxonomy/                      # ◆ BRSR XBRL taxonomy drops (versioned) + form_schema.yaml
├── infra/{terraform,cloudinit,deploy}/
├── ops/                           # backups, runbooks, benchmark scripts
├── docs/{state/{HANDOFF.md,SESSION_LOG.md,BACKLOG.md},adr/,schemas/}
├── testdata/                      # small fixtures; large via make fetch-testdata
├── docker-compose.yml  Makefile  .github/workflows/ci.yml
```

## 2. The verbs
`make up|down` · `make verify` (ruff+mypy+tsc+eslint+all offline tests — the DoD gate) · `make test-api|test-worker|test-fe` · `make migrate` · `make seed` (access fixtures + taxonomy only; never corpus data) · `make ingest-nse-initial|ingest-nse-next|ingest-nse-refresh` (governed real-corpus acquisition) · `make rebuild-metrics` (recompute metrics/scores from extracted_fields — the analytics `reindex` guarantee) · `make fetch-testdata` · `make bench-extraction` ◆ (offline benchmark vs golden set) · `make fmt`

## 3. Code standards (deltas from sibling ◆)
Python ruff/mypy-strict on services+worker; TS strict; every endpoint has response model + success/failure tests; config via pydantic-settings only.
◆ **LLM calls:** only through `services/llm.py`; every call sites a `prompt_key@version`; no inline prompts, ever; tests use committed fixture responses (`prompts/fixtures/`) via the fake client — a test that would hit a live LLM fails CI by design.
◆ **Published-number rule:** any value surfaced on a public page must come from `metrics/scores` materialisations pinned to QA-passed field versions — routers may not read `extracted_fields` for public views (enforced by a lint-style test greping router imports).
◆ **Lineage rule:** any UI element showing a company-level number must carry `source_ref` (filing, page, span) in its API payload.
◆ **Events:** user-facing state changes and all high-intent views emit product events via `services/track.py` (name registry in `events.yaml`; unregistered names fail a test).

## 4. Session protocol — identical to sibling pack
READ (conventions + session spec + HANDOFF + listed files only) → PLAN (≤10 bullets) → BUILD (small conventional commits `feat|fix|test|chore|infra(scope): msg [SNN]`) → ASSURE (session SELF-CHECK + `make verify` green; blockers go behind documented fallbacks or xfail+BACKLOG — never a red handoff) → COMMIT (final: `chore(session): close SNN — handoff written`) → HANDOFF (schema §5, ≤80 lines, overwrite) → REPORT (DoD ✔/✘ table + verify output).

## 5. HANDOFF.md schema
```markdown
# HANDOFF — after SNN (date)
## Repo state: branch/commit · dev services up · migrations head
## Delivered (≤6 bullets, interface-level)
## Contracts next session relies on (exact signatures/routes/tables/prompt_keys/env vars)
## Sharp edges (≤5)
## Env/secrets added (names only)
## Next: SNN+1 — expected entry state
```

## 6. Token discipline
No whole-file pastes; diffs only · frontend/backend cross-reads only when spec lists them · large fixtures via fetch-testdata · files > ~400 lines get split · don't re-explain architecture in replies.
◆ Prompt YAMLs count as code: read only the prompt files your session touches.

## 7. Universal DoD
✔ verify green ✔ tests per QA_PLAN pyramid ✔ no TODO without BACKLOG line ✔ .env.example updated ✔ events registered for new surfaces ✔ HANDOFF+SESSION_LOG written ✔ commits pushed
