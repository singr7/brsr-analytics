# PHASE 3 — Filing Studio (S13–S15)
*The preparation tool: a company assembles its BRSR here. Doctrine: AI drafts, humans decide; nothing exports with unreviewed AI answers; the required format is data, not code.*

---
## S13 — Questionnaire engine & the full format encode
**GOAL:** The complete prescribed BRSR structure as a versioned, data-driven form engine with validations — the compliance skeleton everything else hangs on.

**READ:** HANDOFF, 00_ARCHITECTURE §6, `taxonomy/form_schema.yaml` v0 (S02), studio_* models.

**TASKS**
1. **Full format encode:** extend `form_schema.yaml` + field_defs to the complete BRSR: Section A (entity details, products/services, operations, employees/workers breakdowns, holdings, CSR, transparency), Section B (policy matrix per principle — the 9×~12 policy grid), Section C per principle (Essential + Leadership indicators), BRSR Core KPI annexure, with: field order, tables-as-repeating-groups (e.g., employee categories × gender × permanent/other), conditionality (leadership blocks optional; skip logic), dtypes/units, cross-field relations (totals = sums; % denominators), and `xbrl_concept` mappings per the current exchange taxonomy drop in `taxonomy/` (**pin the taxonomy version used; format-update procedure documented in `taxonomy/README.md`** — new SEBI/exchange release = new schema version + migration note, not code surgery). This is a large data-authoring task: split the YAML per section; write a schema-linter (`make lint-schema`) checking key grammar, relation references, concept coverage; commit section-by-section.
2. Form engine (`worker/studio/` + routers): instantiate a `studio_filing` from schema version → answer CRUD with dtype/unit validation at write; repeating-group handling; progress model (per-section % complete, Core-completeness separately — the number that matters).
3. Validation service tiers (run on demand + on export): L1 field (dtype/unit/range) → L2 relations (totals, % sanity, YoY-vs-prior-filing deltas flagged over threshold) → L3 completeness (required/Core) — results as structured findings `{severity, field_key, message, fix_hint}`.
4. Studio frontend: section navigator with progress rings, form renderer generated from schema (table groups as editable grids; keyboard-friendly), findings panel (click → jump to field), autosave, single-editor lock + comments (per non-goals).
5. Prior-year import: if the company exists in the corpus, offer pinned prior values as pre-fill candidates (marked `author=user` only after explicit accept — provenance discipline from minute one).

**SELF-CHECK:** schema-linter green on full encode · engine renders every section from schema alone (walk test: Playwright traverses all sections of a fixture filing) · validation goldens (a fixture filing with 15 seeded errors → exactly the expected findings) · repeating-group grid e2e · prior-year prefill accept flow · verify green.
**COMMITS:** `feat(schema): full BRSR encode + linter [S13]`, `feat(studio): form engine + validations [S13]`, `feat(fe): studio navigator + renderer [S13]`, close.
**HANDOFF:** schema stats (sections/fields/relations counts), findings schema, engine API, taxonomy version pinned, known encode ambiguities (BACKLOG'd for expert review — flag to human: **domain-expert pass over the encode needed before S15 export sign-off**).

---
## S14 — Doc-to-draft: AI-assisted preparation
**GOAL:** Upload the company's real documents → reviewed draft answers with evidence — the "prepare with some docs" magic, governed.

**READ:** HANDOFF, `services/llm.py`, S06 extraction patterns (reuse hard), studio_docs model.

**TASKS**
1. Document intake: upload (PDF/DOCX/XLSX) → type classification prompt (policy doc, HR report, energy/utility data, sustainability report, prior BRSR, CSR report, other) → parsed via the S05 machinery (pages, text, images, embeddings) into a per-org private corpus (strict org isolation — test it like a tenant boundary).
2. Mapping engine (`worker/studio/mapper.py`): per section, retrieve candidate evidence (vector + keyword over org corpus) → mapping prompts (`prompts/studio_map_*.yaml`) proposing `{field_key, proposed_value, unit, evidence: {doc, page, quote}, confidence}` — **verbatim-quote tripwire reused from S06**; proposals land as `studio_answers(author='ai', review_status='unreviewed')`, never overwriting user answers.
3. Review UX: per-section "AI proposals" lane — side-by-side proposed value + evidence snippet (lineage-viewer component reused) with accept / edit-accept / reject; bulk accept only within high-confidence band (policy); every decision evented.
4. Gap intelligence: after mapping, a **document-gap report**: which sections have no evidence in the uploaded corpus + what document types would fill them ("no energy data found — upload utility statements or DISCOM bills") — the feature that makes users bring more data AND the natural Bioedge conversation starter (evented as high-intent).
5. Cost/quota: per-org token metering (S06 accounting reused), Studio-tier quotas, size caps.
6. Fixtures: a synthetic company doc-pack (5 small constructed docs) → golden mapping proposals; org-isolation adversarial test (org B never retrieves org A's chunks — parametrised over every retrieval path).

**SELF-CHECK:** mapping goldens ≥ target on fixtures · quote tripwire test · isolation adversarial suite green · unreviewed-AI answers excluded from validation-passing and progress "complete" states · gap report golden · verify green.
**COMMITS:** `feat(studio): doc intake + classification [S14]`, `feat(studio): mapping engine + review lane [S14]`, `feat(studio): document-gap report [S14]`, close.
**HANDOFF:** mapper contract, proposal states, gap-report schema, quota knobs, isolation test locations.

---
## S15 — Exports: XBRL, board draft, assurance-readiness gap report
**GOAL:** The Studio's deliverables: taxonomy-valid XBRL for submission prep, a polished document draft, and the gap report that doubles as the lead magnet.

**READ:** HANDOFF, `taxonomy/` drop + concept mappings (S13), WeasyPrint patterns, validation findings schema.

**TASKS**
1. **XBRL instance generator** (`worker/exportgen/xbrl.py`): studio answers → instance document against the pinned exchange taxonomy (contexts, units, decimals per concept; repeating groups → tuples/dimensions per taxonomy design); **arelle validation pass required** — validator output parsed into the findings schema; export blocked on L1/L2/arelle errors and on any `ai_unreviewed` required field (the doctrine gate, enforced here, tested hard).
2. Document draft: full BRSR as formatted PDF + DOCX (python-docx) in the conventional presentation order — cover, Section A/B/C with tables, annexures; watermark `DRAFT — prepared with BRSR Lens` (removable at final status); a change-log appendix (answers + authorship trail — assurance-friendly provenance).
3. **Assurance-readiness gap report:** validation findings + Core coverage + evidence coverage (which answers carry evidence vs bare assertions) + peer-percentile preview (via S08, if company in corpus) → scored report with prioritised fix list; rendered PDF; **final page: clearly-labeled "How Panacea Bioedge can help" with the specific gaps as the agenda** — generated, contextual, honest; `studio_gap_report` event (top lead-signal weight).
4. Export management: async generation, versioned artifacts to S3, presigned downloads, export history per filing; re-export invalidated on answer changes (staleness flag).
5. **Submission-prep note** rendered into every export package: what the files are, what the company/its advisors must do to actually file (portal steps live outside us), and the liability line (per non-goals — we produce validated files; we do not submit).

**SELF-CHECK:** fixture filing → arelle-clean instance (golden) · export-block matrix test (each blocking condition individually trips) · DOCX/PDF structural goldens · gap report golden incl. the Bioedge page rendering from real findings · staleness flag e2e · verify green.
**COMMITS:** `feat(export): xbrl generator + arelle gate [S15]`, `feat(export): draft pdf/docx + provenance appendix [S15]`, `feat(export): gap report + engagement page [S15]`, close.
**HANDOFF:** export API, artifact layout, blocking-conditions table, taxonomy-update procedure pointer. **Flag to human: domain-expert sign-off on one full fixture export (XBRL + draft) before Studio goes to any real company.** Next: S16 (PHASE4).
