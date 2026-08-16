# UX gate — UNSIGNED

Per DEPLOYMENT.md §5, the UX owner confirms that the comprehension, accessibility, expert-bypass
and upload-privacy checks remain valid **on the deployed release candidate**, not only in CI.

## What the UX owner is asked to confirm

- Five-second comprehension check with at least three reviewers on `/`, `/explore`, `/sectors`.
- Zero axe violations on public routes; Home performance at or above 85.
- Expert bypass reaches the full `/ask` workspace from every guided question.
- Upload privacy language is correct on the Studio and Deep Dive surfaces.
- Keyboard and visual walk across guided questions, tier locks, follow-ups, error and
  suppression states, and URL reload behaviour.

## Standing blocker

The browser runtime has been unavailable in every session that attempted this pass, so the visual
and keyboard walks listed in `docs/state/BACKLOG.md` are still outstanding. Component tests,
responsive CSS review, live HTTP checks and production-build checks have passed in their place.
This gate cannot be signed on automated checks alone.

## Sign-off

| Field | Value |
|---|---|
| Reviewer | _unsigned_ |
| Date | _unsigned_ |
| Release candidate | _unsigned_ |
| Outstanding exceptions | browser-based visual/keyboard pass not yet performed |
