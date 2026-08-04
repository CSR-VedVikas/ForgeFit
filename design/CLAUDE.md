# ForgeFit — project instructions

## Pending deliverable (requested 28 Jul 2026)

When the project work is complete, produce a **full engineering report** — the
project explained the way an SDE would explain it to another SDE, covering every
iteration in detail, not a summary:

- The starting point: the original ForgeFit UI (light, clinical, low hierarchy)
  and the specific pain points that drove the redesign.
- Every design decision and *why*, including options that were rejected —
  the ink-vs-light ground call, caps exercise names, Lucide nav icons, the
  record moment as a footer slab rather than the old full-screen burst.
- Screen-by-screen build notes for all eight screens plus landing/auth.
- Technical problems hit and how they were diagnosed and fixed — notably the
  percentage-height bug where the app root resolved against an auto-height
  wrapper (fixed with `position:absolute; inset:0`), and the PR panel's
  animation being stranded by per-second re-renders (moved to state-driven).
- The state model: what lives where, and how settings propagate into the
  session sheet.
- The security audit: all 11 findings, severities, and the reasoning behind the
  phase ordering in the completion plan.
- What remains, and the open decisions the user still owns.

Chronological, with file names and specifics. Written for an engineer picking
the project up cold.
