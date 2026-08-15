# HANDOFF — after S15 / Phase 3 (2026-08-15)

## Repo state: `main` · Phase 3 committed · dev services up · migrations head `0006`

## Delivered

- Schema `1.0.0` expands `taxonomy/form_schema.yaml` plus `sections/format.yaml` into the full
  Studio catalog. `make lint-schema` validates grammar, unique concepts, references, coverage and
  reports sections/fields/relations/Core counts. Taxonomy release is pinned in `taxonomy/README.md`.
- Filing API is under `/api/studio`: schema, filing CRUD, answer autosave, validation, progress,
  comments/editor lock, prior candidates, private documents, mapping/review, gaps and exports.
- Findings are `{severity, field_key, message, fix_hint, tier}` with L1 dtype/unit/range, L2
  relations/YoY and L3 required/Core/review governance.
- Studio document intake accepts matching PDF/DOCX/XLSX up to `STUDIO_DOCUMENT_MAX_BYTES`; every
  retrieval path filters `studio_org_id`. Proposals preserve document/page/verbatim quote and remain
  separate from user answers until an explicit decision.
- Exports generate XBRL, draft DOCX/PDF and assurance-gap PDF. L1/L2/L3 or taxonomy errors block
  filing drafts; every answer change marks export history stale. Gap reports remain available.
- `/studio` provides section/Core progress, schema-rendered inputs, findings jump links, evidence
  upload, proposal review and export-package generation.

## Contracts next session relies on

- Worker entry points: `worker.studio.engine`, `worker.studio.mapper`,
  `worker.exportgen.xbrl`, `worker.exportgen.documents`.
- Prompt keys reserved for live evolution: `studio_classify@v1`, `studio_map_section@v1`.
- Storage layout: `studio-docs/{studio_org_id}/...` and
  `studio/{filing_id}/v{version}/brsr.{xbrl|docx|pdf|gap.pdf}`.
- Config: `STUDIO_DOCUMENT_MAX_BYTES`, `STUDIO_MONTHLY_TOKEN_LIMIT`,
  `STUDIO_BULK_ACCEPT_CONFIDENCE`.

## Sharp edges

- Arelle is invoked when `arelleCmdLine` is installed; local CI uses the deterministic instance
  structural validator because the official taxonomy package is not redistributed here.
- Domain-expert schema and one-fixture export sign-off are mandatory before real-company use.
- The committed mapper is deterministic/offline and needs accuracy benchmarking on reviewed,
  lawfully supplied document packs before enabling a live provider.

## Next: S16 — engagement analytics and lead routing

Preserve the `studio_gap_report` and Phase 3 review/export events as high-intent input signals.
