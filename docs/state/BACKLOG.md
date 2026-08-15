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
