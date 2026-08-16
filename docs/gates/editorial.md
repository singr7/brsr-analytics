# Editorial gate — UNSIGNED

Per DEPLOYMENT.md §5, the editorial owner confirms per-family accuracy against target before any
pin-to-public, using `/admin/quality` and the publication thresholds as the mechanism. Families
below target stay gated with confidence flags.

## What the editorial owner is asked to confirm

- Per-family accuracy at or above `PUBLISH_FAMILY_ACCURACY_TARGET` (0.98) on `/admin/quality`.
- Benchmark representativeness and the substance index in `docs/methodology/substance_index.md`.
- The methodology page matches the committed scoring configuration.
- The correction channel works end to end.

## Open item: the published-number rule was narrowed for the NSE corpus

This needs an explicit editorial decision, not a silent inheritance.

01_CONVENTIONS §3 states that any value on a public page must come from materialisations pinned
to **QA-passed** field versions. Migration `0010` rewrites the `validate_field_version_pin`
trigger so that a field with `qa_status='provisional'` may also be pinned, provided it carries
NSE mapping lineage (`source='nse_brsr_xbrl'` and a non-null `mapping_id`).

This is deliberate and narrowly scoped, and it is what allows the FY25 NSE cohort to reach
Explorer at all. But the guarantee is now "QA-passed, or provisional with declared NSE mapping
lineage" rather than "QA-passed only". Confirm this is the intended launch posture, or require
the FY25 cohort to be QA-reviewed before public exposure.

Supporting context:

- The 16 concept mappings, their assumptions and confidences are reviewable at `/admin/ingestion`
  and recorded in `taxonomy/nse_concept_mappings.yaml`.
- Turnover scale now resolves from a reviewed per-issuer registry and **withholds** rather than
  guesses for unregistered issuers; see `docs/operations/NSE_METRIC_MAPPING_REVIEW.md`.
- `MtCO2e` is still provisionally read as metric tonnes (confidence 0.80) and remains the first
  domain-review priority.
- `/explore` carries a visible provisional caveat while this gate is unsigned.

## Open item: cohort suppression minimum lowered from 8 to 5

`minimum_sector_size` and `minimum_cohort_size` are now `5`, so sector aggregates publish at five
companies instead of eight. This is the anti-reidentification guard: at n=5 a company is one of
five in its sector cell, making sector-relative positioning easier to attribute to a specific
filer. On the current cohort it newly exposes Financial Services (n=6). Confirm the threshold.

## Sign-off

| Field | Value |
|---|---|
| Reviewer | _unsigned_ |
| Date | _unsigned_ |
| Families cleared to public | _none_ |
| Provisional NSE pins permitted on public surfaces | _undecided_ |
