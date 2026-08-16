# Substance and readiness score methodology

> Auto-generated from `scoring.yaml`; edit the configuration, not this file.

Method version: **1.1.0-provisional-nse**

## Completeness

Completeness is weighted field coverage on the QA-pinned disclosure set. BRSR Core fields
carry weight **2.0** and remaining Essential fields carry weight
**1.0**. Components retain both present and possible counts.

## Substance versus boilerplate

The index combines quantified targets (35%),
dated commitments (25%), named methodologies
(20%), and corpus originality
(20%). Near-verbatim
8-word phrases appearing in at least
3 companies are treated as boilerplate. The
shared-phrase table is regenerated from the pinned corpus on every rebuild.

## Assurance readiness

Assurance status contributes 40%, BRSR Core
coverage contributes 35%, and complete source
lineage contributes 25%.

## Cohorts and reproducibility

Sector percentiles are suppressed below **5** companies.
Every score stores its method version, component values, configuration hash, and a pinned
field-version anchor. `make rebuild-metrics` is a deterministic full rebuild.
