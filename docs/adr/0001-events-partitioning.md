# ADR 0001: Native monthly event partitions

Status: accepted (S02, 2026-08-14)

## Decision

Use PostgreSQL native range partitioning on `events.ts`. The initial migration creates
monthly partitions from 12 months before migration time through 24 months after it,
plus a default partition. This is the "pg_partman-style manual DDL" option: it avoids
an extension dependency while retaining predictable monthly tables and safe routing
outside the pre-created window.

Before production, a scheduled maintenance task will create the next month's partition
and move any matching rows out of `events_default`. Partition names use `events_YYYY_MM`.
