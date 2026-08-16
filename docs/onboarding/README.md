# Onboarding and demo material

Two standalone HTML pages. No build step, no dependencies, no network calls — open either
file directly in a browser, or serve the directory.

| File | What it is | Audience |
|---|---|---|
| `field-guide.html` | Click-through guide to the whole portal: every route, the three journeys, the seven-stage ingestion pipeline, publishing governance, operator commands, admin surfaces, known limits, glossary | Incoming PMs and the maintaining team |
| `fy25-in-100-filings.html` | Self-playing twelve-scene walkthrough (2 min 42 s) of the FY25 NIFTY 100 corpus, with switchable narration tracks for a business sponsor and a sustainability lead | Sponsors, prospects, internal demos |

## Provenance of the figures

Every number in both pages was read from the live FY 2024–25 database on **16 August 2026**:
100 registry companies, 93 parsed filings, 7 recorded missing, 204,880 raw XBRL facts,
1,255 pinned fields across 92 filings, 1,527 metrics and 351 scores under scoring method
`1.1.0-provisional-nse`. Nothing is illustrative or synthetic.

The lineage example is a real chain: Hindustan Unilever's renewable energy figure of
3,444,905 GJ, its pinned field version, the `TotalEnergyConsumedFromRenewableSources`
mapping, the raw fact in context `DCYMain`, and the source document
`BRSR_1486091_18072025110717_WEB.xml` with its SHA-256.

## Keeping them current

These are point-in-time snapshots, not generated views. After a cohort ingest or a
methodology version bump the figures go stale, so re-read them from the database and edit
the two files. The queries behind each scene are ordinary aggregates over `metrics`,
`scores`, `companies` and `filings`.

Both pages carry the provisional-corpus caveat. Keep it. All sixteen NSE concept mappings
are still `provisional` pending domain review, and the three gates under `docs/gates/`
are unsigned.

## Producing a video from the walkthrough

`fy25-in-100-filings.html` is timed and self-advancing. Open it full-screen, press play
from scene 1, and screen-record for the 2 min 42 s runtime. The narration text under the
stage is the voice-over script — record either track, or both for two edits of the same
footage.
