# HANDOFF — after S02 (2026-08-14)

## Repo state: `main` · dev services up · migrations head `0001`

## Delivered

- Initial Alembic migration and typed SQLAlchemy models for the complete relational spine.
- Append-only extracted-field versions with same-field/same-filing composite pin integrity;
  a database trigger permits only `sampled_ok` or `corrected` values to be pinned.
- Metrics and scores require a `field_version_pins` FK; public materialisations cannot
  reference raw or unreviewed extraction versions directly.
- PostgreSQL `vector(1024)` embeddings with cosine IVFFlat index and native monthly
  event partitions, including a safe default partition.
- `taxonomy/form_schema.yaml` v0.1.0 with 120 representative fields and an idempotent
  validated upsert loader.
- Idempotent seed with 20 companies, 40 filings, deliberate gaps/outliers, demo users
  at all four tiers, and one Studio organisation/draft.

## Contracts next session relies on

- Tables: `companies`, `filings`, `filing_pages`, `field_defs`, `extracted_fields`,
  `field_version_pins`, `metrics`, `scores`, `embeddings`, `users`, `orgs`,
  `memberships`, `plans`, `api_keys`, `events`, `leads`, `deepdive_requests`,
  `studio_orgs`, `studio_filings`, `studio_answers`, `studio_docs`.
- Extraction identity: unique `(filing_id, field_key, version)`; versions are positive.
- Pin identity: unique `(filing_id, field_key)`; `extracted_field_id` must match both and
  its `qa_status` must be `sampled_ok|corrected`.
- Public materialisations: `metrics.field_version_pin_id` and
  `scores.field_version_pin_id` are required FKs to `field_version_pins.id`.
- Field grammar: `a.<section>.<name>` or `pN.<section>.<name>`; nested KPI groups are
  allowed, e.g. `p6.e1.energy_total_gj`. Segments are lowercase snake_case.
- Loader: `load_form_schema(path=None) -> (version, fields)` and
  `upsert_field_defs(session, path=None) -> count`.
- Database: `create_engine(settings=None)` and `create_session_factory(engine)`.
- Commands: `make migrate`; `make seed` (safe to rerun).
- Event partitions: `events_YYYY_MM`; migration creates -12/+24 months and
  `events_default`. Choice is documented in `docs/adr/0001-events-partitioning.md`.

## Sharp edges

- Demo password hashes are placeholders until S03 implements Argon2 authentication.
- Event-partition maintenance scheduling is a production-infrastructure concern for S18;
  the default partition safely accepts dates outside the pre-created window meanwhile.
- Seed sources and values are explicitly synthetic and must never be presented as real.

## Env/secrets added

None.

## Next: S03 — expected entry state

Run `make up && make migrate && make seed`; build auth and live event persistence on the
existing users/orgs/plans/memberships/events contracts without weakening pin invariants.
