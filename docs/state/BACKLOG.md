# Backlog

- Manual visual browser pass for the S03 signup/login/org-switcher surfaces and a browser-
  observed pageview row. The in-app browser bridge could not initialize during S03; live
  API persistence and the frontend beacon component test passed.
- Human legal gate: approve individual acquisition sources in `worker/acquire/SOURCES.md`;
  keep all automated-source flags disabled until then.
- Human editorial gate: review `/api/admin/quality`, publication thresholds, benchmark
  representativeness, and `docs/methodology/substance_index.md` before public exposure.
- Grow the S06 golden extraction corpus to QA_PLAN's ≥400 values across ≥25 lawfully obtained
  real filings; current committed CI fixture is intentionally synthetic and small.
- Run the Phase 2 browser/axe/Lighthouse and visual screenshot pass when the in-app browser bridge
  is available; its host integration could not initialize in this session. Target Home performance
  remains ≥85 and public-route axe violations must be zero.
- Mandatory Phase 3 domain-expert gate: review the complete schema encode against the current
  exchange format and sign off one full fixture XBRL plus draft document before any real company
  uses Studio. The bundled taxonomy namespace is deterministic for local validation; install the
  official current exchange taxonomy drop and run Arelle against it for production submission prep.
- Replace the deterministic local Studio mapper with live accuracy runs after building a reviewed
  synthetic/consented five-document golden pack; offline CI intentionally remains provider-free.
- Run a visual and keyboard pass on the S16 `/deep-dive`, `/privacy`, `/admin/analytics`, and
  `/admin/leads` surfaces when the in-app browser host bridge is available. Component/type/lint
  checks and live API smoke tests passed in S16; browser initialization remained unavailable.
- Run a visual and keyboard pass on the S17 config-driven `/pricing` and invoice `/billing`
  surfaces. The in-app browser could not create a session; component tests, responsive CSS review,
  TypeScript/ESLint and rebuilt-service route smoke checks passed instead.
- Run the S18 five-second comprehension check with three internal reviewers and a desktop/mobile
  visual keyboard walk across `/`, `/sectors`, `/assurance`, `/studio`, and `/ask`. The browser
  runtime exposed no available browser; route, responsive-navigation, Escape/focus, auth/org,
  terminology, metadata, and privacy-safe event contracts passed automated tests.
- Run the S19 desktop/mobile visual and keyboard walk across all eight `/explore` questions,
  advanced controls, tier locks, suggested/custom follow-ups, error/suppression states, and URL
  reloads. The browser runtime again exposed no available browser; live HTTP, component interaction,
  responsive CSS, context-merge, privacy, production-build, and full verification checks passed.

## Pre-production review (2026-08-16)

All P0, P1 and P2 items raised by this review were actioned in the same pass. What remains is
listed under "Still open" below; everything else is resolved and covered by tests.

### Resolved

- **Turnover scale is no longer inferred from magnitude.** `infer_nifty_turnover_scale` published
  Coal India 10x low (reported `143368.92` is INR crore, about INR 1.43 lakh crore; the million
  branch published about INR 14,337 crore), which put it second-worst on energy intensity at
  1,331.68. Dr. Reddy's `231154` sits in the same band and there million *is* correct, so no
  threshold could separate them. Replaced with the reviewed `turnover_scale` registry in
  `taxonomy/nse_concept_mappings.yaml`: above 1e9 the value is unambiguously absolute, below it an
  explicit per-issuer entry is required, and an unregistered issuer is **withheld, not guessed**
  (reported as `withheld=<n>`). Coal India now publishes INR 1,43,369 crore and an energy
  intensity of 133.17, mid-cohort.
- **`decimals` is retained on raw facts** (`xbrl_facts.decimals`, migration `0011`), closing the
  gap against the "losslessly persisted" claim. It is recorded in extraction lineage and is
  explicitly *not* used for scale: FY25 shows Coal India `decimals="2"` (crore), Dr. Reddy's
  `decimals="0"` (million) and Infosys `decimals="2"` (absolute), so precision and scale are
  independent.
- **Production config guards extended.** `production_secrets_are_safe` now rejects
  `AUTH_EXPOSE_VERIFICATION_TOKEN=true` and `LLM_PROVIDER=fake` when `APP_ENV=production`,
  alongside the existing JWT check. Previously a production deploy that forgot the flag would
  return verification and org-invite tokens in API responses.
- **Plausibility screens added** (`scoring.yaml`, `screen_implausible`). These assert arithmetic
  identities the disclosure makes about itself — energy total equals renewable plus
  non-renewable, water withdrawal equals the sum of its sources — at 1% tolerance, plus
  non-negativity. A failing metric is withheld along with everything derived from it. Deliberately
  no emissions-per-energy band: Scope 1 legitimately includes non-energy fugitive and process
  emissions, so such a band would encode a false rule. All 25 FY25 filings pass.
- **Multi-source metrics carry full lineage.** `metrics.contributing_pin_ids` (migration `0011`)
  records every contributing pin, so Scope 1+2 carries both scope pins and an intensity carries
  its numerator and denominator pins, instead of anchoring to the first component only.
- **Launch gate files created** under `docs/gates/` (`legal.md`, `editorial.md`, `ux.md`, plus an
  index), which DEPLOYMENT.md §5 makes a hard prerequisite. All three are explicitly UNSIGNED.
  The editorial gate carries the open decision on migration `0010` narrowing the published-number
  rule to allow provisional NSE pins on public surfaces.
- **`/explore` banner rewritten for its actual audience.** It previously showed anonymous
  visitors an internal instruction to review mappings under Admin. It now explains provisional
  status and links to methodology, and shows the Admin pointer only to admins.
- **Compose/runtime parity fixes.** `mailhog` host ports parameterized
  (`MAILHOG_SMTP_PORT`/`MAILHOG_UI_PORT`) so the stack no longer collides with a sibling project;
  `taxonomy/`, `scoring.yaml` and `plans.yaml` mounted so api and worker stop running stale baked
  config (the live catalog was serving `1.0.0` with none of the new measures); `./worker` mounted
  into `api` so the documented `docker compose exec api python -m worker...` commands run current
  code.
- **`test_production_rejects_default_jwt_secret` no longer reads the developer's `.env`**, so the
  guard is actually exercised. `make verify` was red locally before this.
- `docs/operations/NSE_METRIC_MAPPING_REVIEW.md` corrected: it previously cited Coal India as
  evidence the heuristic produced plausible magnitudes.

### Thin cohorts are now shown with a footnote, and the minimum is 5

Two related changes, both requested.

`minimum_sector_size` (`scoring.yaml`) and `minimum_cohort_size` (`taxonomy/semantic.yaml`) are
now `5`, along with the `materialize_percentiles` default and the UI copy.

Results below the minimum are no longer blanked. Rows carry `thin_cohort: true` and the query
returns a footnote — "N of these results cover fewer than 5 companies (n=…). They are shown with
what has been ingested so far, but the cohort is too thin for incisive comparison." The charts
render the data instead of the old "Cohort protected" blocking state. On the 50-company corpus,
all 15 sectors return values and 12 are flagged.

Sector *percentiles* (`percentile_sector`) are still withheld below the minimum. Showing an
aggregate computed from three companies is defensible with a caveat; ranking a company against
two peers is not, so that split is deliberate.

Note for the editorial gate: the cohort minimum is the anti-reidentification guard, and showing
thin cohorts rather than hiding them reduces its protection. With n=1 sectors now visible, a
single-company sector aggregate is that company's own value. This is recorded rather than
assumed — see `docs/gates/editorial.md`.

### Still open

- **Re-ingest to populate `decimals` on existing facts.** The column and parser are in place, but
  the 25 FY25 filings already in the database were parsed before it existed, so their
  `xbrl_facts.decimals` is null and lineage records `reported_decimals: null`. A re-ingest of the
  cohort backfills it. No published number depends on this.
- **Single-file bind mounts pin an inode**, so editing `scoring.yaml` or `plans.yaml` while the
  stack runs does not propagate until the service restarts. Noted in `docker-compose.yml`.
  Moving root config into a mounted directory would remove the footgun.
- **`compose.prod.yml` (DEPLOYMENT.md §1) does not exist** and `infra/{terraform,cloudinit,deploy}`
  are empty, so the §4 release flow is not yet executable. This is infrastructure build-out rather
  than a defect in the application, and is the largest remaining gap before a production turn-up.
- **`MtCO2e` remains provisionally read as metric tonnes** (confidence 0.80) and is still the
  first domain-review priority in `/admin/ingestion`.

