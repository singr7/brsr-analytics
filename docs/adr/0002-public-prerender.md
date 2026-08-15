# ADR 0002: Static rendering boundary for public citation pages

## Decision

Public sector and methodology routes use stable, path-based permalinks, route-specific document
titles, and citation metadata. Production deployment prerenders `/`, `/sectors`, `/materiality`,
`/assurance`, and `/methodology` after the API seed/materialisation step. The Vite SPA remains the
hydration target so URL-persisted filters and chart interactions work unchanged.

## Rationale

The application has a small, known public route set but data is refreshed by governed
materialisation runs. A deploy-time route snapshot gives crawlers and citation tools deterministic
HTML without introducing a second rendering framework or a second query implementation.
