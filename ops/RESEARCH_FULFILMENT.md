# Research dataset fulfilment

`GET /api/export/dataset?format=csv|parquet` is self-service for Research licences and contains
only governed, public-measure sector aggregates. Both formats embed the licence notice; cohorts
smaller than the semantic catalog minimum are excluded.

Full-corpus requests are manual:

1. Confirm the organisation has an active Research licence and record permitted users, purpose,
   fields, financial years, delivery format, retention period and redistribution terms.
2. Get legal/editorial approval for the requested source material and measures. Never fulfil from
   raw `extracted_fields`; use QA-pinned materialisations and include lineage identifiers.
3. Generate into a per-request object-store prefix, attach a checksum manifest, methodology/catalog
   versions and the signed licence notice, then provide a time-limited delivery link out of band.
4. Record delivery date, checksum, approver and expiry in the customer ticket. Revoke the link at
   expiry and retain only the audit record required by the agreed term.

Scoped API keys are issued and revoked by an organisation owner under `/api/research/keys`. A key
secret is shown once, stored only as SHA-256, rate-limited per key, and must carry `query:read`
and/or `dataset:read`. The query contract is documented in the service OpenAPI page at `/docs`.
