# BRSR taxonomy and form schema

The Studio pins form schema `1.0.0` to the BSE/NSE BRSR XBRL taxonomy release dated
2024-05-31. `form_schema.yaml` contains the established field catalog and loads section data from
`sections/format.yaml`. Templates are expanded deterministically into ordinary field definitions;
the runtime never hard-codes a regulatory question.

## Updating the format

1. Store the new exchange taxonomy drop under a versioned `taxonomy/drops/<release>/` directory.
2. Copy the current schema, change `schema_version` and taxonomy release/namespace, then update
   section data, concept mappings, conditions and relations.
3. Add a migration note under `taxonomy/migrations/<old>-to-<new>.md`, including renamed fields and
   safe prefill mappings. Never change the meaning of a field key in place.
4. Run `make lint-schema` and the export golden tests, then obtain a BRSR domain-expert review of
   one complete fixture before enabling the version for real filings.

The bundled namespace is a deterministic local validation namespace for submission preparation.
Before production filing, replace the placeholder taxonomy package with the currently published
exchange drop and complete the mandatory domain-expert/XBRL sign-off recorded in the backlog.
