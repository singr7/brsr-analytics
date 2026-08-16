# Provisional NSE metric mapping and domain review

## Purpose and publication status

This module turns the losslessly retained NSE BRSR XBRL facts into a small, comparable FY25
Explorer layer for domain review. It is deliberately labelled **provisional**. Publication here
means visible inside the local BRSR Lens Explorer; it is not a claim that a domain expert or
assurance practitioner has approved the mapping.

The source-of-truth proposal is `taxonomy/nse_concept_mappings.yaml`. Migration `0010` persists
each proposal, its confidence, rationale, assumption, conversion rules, review status, reviewer
notes and timestamps in `nse_concept_mappings`.

## Selection assumptions

- Use the fact whose period ends on 31 March of the selected `fyTo`.
- Use XBRL context `DCYMain` as the current-year entity-wide value; dimensional plant, area,
  workforce and prior-year contexts are excluded.
- Preserve the original fact, unit, context, period, reported `decimals`, resolved scale and
  mapping identifier in extraction lineage.
- Provisional mappings are separately marked in `extracted_fields.qa_status`; the database trigger
  permits them to be pinned only when NSE mapping lineage is present.

## Common-unit conversions

| Family | Reported unit | Published unit | Conversion / assumption |
|---|---:|---:|---|
| Energy | MJ | GJ | multiply by 0.001 |
| Energy | GJ | GJ | unchanged |
| Energy | TJ | GJ | multiply by 1,000 |
| Water | kL | kL | unchanged |
| Emissions | tCO2e | tCO2e | unchanged |
| Emissions | ktCO2e | tCO2e | multiply by 1,000 |
| Emissions | `MtCO2e` | tCO2e | provisionally unchanged; issuer magnitudes indicate “metric tonnes”, not megatonnes |

The `MtCO2e` interpretation has 0.80 confidence and is the first domain-review priority. Treating
values such as an IT issuer's reported `8,745 MtCO2e` as 8.745 billion tonnes would be physically
implausible. The proposal therefore treats NSE's token as a metric-tonne label, while retaining the
reported token for review.

## Turnover normalization

NSE instances in this cohort use the `INR` unit token but mix absolute INR and scaled values, and
the reporting scale cannot be recovered from the instance document:

- the unit token is `INR` for every issuer regardless of scale;
- the XBRL `decimals` attribute is a precision claim, not a scale factor. Observed FY25: Coal
  India `decimals="2"` value `143368.92` (crore), Dr. Reddy's `decimals="0"` value `231154`
  (million), Infosys `decimals="2"` value `1289330074464.23` (absolute INR). Precision and scale
  are independent, so `decimals` cannot disambiguate. It is retained on `xbrl_facts.decimals` for
  provenance and must not be used to infer scale.

An earlier build inferred scale from magnitude (`>= 100,000` was read as INR million). That is
unsound and it published a materially wrong number: Coal India's `143368.92` is INR **crore**,
about INR 1.43 lakh crore, but the million reading published about INR 14,337 crore — an order of
magnitude below the filed financials — which in turn overstated Coal India's energy and emissions
intensity roughly tenfold and placed it second-worst in the cohort. Dr. Reddy's `231154` sits in
the same numeric band and there the million reading *is* correct, so no threshold separates the
two cases.

Scale is therefore resolved from the reviewed `turnover_scale` registry in
`taxonomy/nse_concept_mappings.yaml`:

- value `>= absolute_threshold` (1,000,000,000): already absolute INR, because a crore or million
  reading would imply an economically impossible turnover;
- below the threshold: the issuer must have an explicit registry entry giving `scale`,
  `confidence` and `evidence`;
- an unregistered issuer in the ambiguous band is **withheld, not guessed**. Its turnover is not
  pinned and every turnover-normalized intensity is withheld for it. The publish command reports
  these as `withheld=<n>`.

Extending the corpus beyond the current cohort therefore requires adding registry entries for any
new issuer that reports below the threshold, rather than trusting a heuristic.

Explorer computes:

```text
energy intensity    = converted energy GJ / turnover INR × 10,000,000
water intensity     = water withdrawal kL / turnover INR × 10,000,000
emissions intensity = (Scope 1 + Scope 2 tCO2e) / turnover INR × 10,000,000
```

Absolute totals remain available beside normalized measures so reviewers can detect scale and
boundary effects. These rankings describe reported data; they are not performance ratings.

## Plausibility screens

`scoring.yaml` declares arithmetic identities the disclosure asserts about itself — total energy
must equal renewable plus non-renewable, and total water withdrawal must equal the sum of its
source categories — with a 1% tolerance, plus a non-negativity list. A component reported at a
different scale from its total breaks these, which is the failure mode that unit and scale
mistakes actually produce. A metric that fails a screen is withheld from materialization along
with everything derived from it, for that company and year only.

There is deliberately **no** emissions-per-energy band. Scope 1 legitimately includes non-energy
fugitive and process emissions — Coal India's mine methane is the clear case in this cohort — so
such a band would encode a rule that is not true and would suppress correct data. Ratio outliers
belong in reviewer judgement, not in an automated gate.

All 25 FY25 filings currently pass both identities.

## Publish and refresh commands

Publish mappings and rebuild Explorer from already-ingested facts:

```sh
make publish-nse NSE_FY=2025
```

Pull the next ten official companies, map them and rebuild Explorer in one command:

```sh
make ingest-nse-next NSE_FY=2025 NSE_LIMIT=10
```

Docker equivalent:

```sh
docker compose exec api python -m worker.acquire.cli next --fy 2025 --limit 10 --publish
```

Scheduled NSE refreshes also re-run mapping and materialization. Repeated publication reuses an
unchanged mapped fact rather than creating duplicate versions.

## Domain-review workflow

1. Sign in as a platform administrator and open `/admin/ingestion`.
2. Open **Provisional NSE concept mappings**.
3. Inspect the governed field, original NSE concept, common unit, confidence, conversion rules,
   rationale and assumption.
4. Set the row to `accepted`, `needs_review` or `rejected`, add notes, and save.
5. Re-run `make publish-nse`. Rejected mappings are unpinned from NSE filings; accepted and
   provisional mappings remain materialized.
6. Present Explorer with a visible provisional caveat until the relevant domain owners accept the
   mappings.

Primary references:

- NSE XBRL filing information: `https://www.nseindia.com/static/companies-listing/xbrl-information`
- SEBI BRSR Core circular: `https://www.sebi.gov.in/legal/circulars/jul-2023/brsr-core-framework-for-assurance-and-esg-disclosures-for-value-chain_73854.html`

SEBI states that BRSR Core provides a base methodology and that industry-specific adjustments or
estimations should be disclosed. This review workspace retains those assumptions rather than
hiding them inside code.
