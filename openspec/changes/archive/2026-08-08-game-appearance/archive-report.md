# Archive Report: game-appearance

**Change**: game-appearance (Duolingo-style appearance for adults)
**Status**: COMPLETE · **Verdict**: PASS (verify-report.md, orchestrator-inline)
**Archived**: 2026-08-08 · **Branch**: merged to main via PRs #31 → #32 → #33 (merge commit `f1ec104`)

## Final State

- All 3 stacked PRs merged to main in order, each CI-green at merge time (browser-smoke + test; fresh merge refs via update-branch).
- Service restarted; live app serves the new appearance (stamp `f1ec104`).
- Test totals at close: **361 pytest** (baseline 349 + 12) · **93 node:test** (88 + 5) · pyright **0 errors** · smoke **31/31** (real Chromium).
- Spec synced: `openspec/specs/game-appearance/spec.md` (new capability, full spec).

## What Shipped

1. **Foundation (PR #31)**: `:root` design tokens (radius/shadow/space scales, `--fox #eb892c`, `--gold #f5c518`, font tokens; brand anchor `#2f7d54`), self-hosted Baloo 2 (OFL) woff2 400/600 with versioned `@font-face` + system-ui fallback, fox favicon (diamond removed), 4-location palette lockstep drift-guard, gate asserts for tokens/favicon/stamps.
2. **Components (PR #32)**: fox mascot header lockup, dots-only wizard indicator, streak flames (`dataset.streakActive`), reward chips + progress track, button press physics, 48px touch targets, token-driven charts (hardcoded hex removed), toast class-swap reveal, `:focus-visible` fox ring, mobile single-column collapse, full `prefers-reduced-motion` gate (no `@starting-style`).
3. **Motion (PR #33)**: `shouldCelebrate` pure helper + `fireConfetti` (first-render suppression, `matchMedia` gate), flame pulse + confetti keyframes neutralized in reduced-motion block, smoke `.mascot`/`.flame` selector asserts.

## Follow-ups (non-blocking)

- gga `STRICT_MODE` 30-line verdict window false-negatives on verbose reviews (3× this change, every verdict PASSED) — consider project `.gga` with `STRICT_MODE=false` or a wider window.
- Pre-existing chart-tooltip hover quirk (drawChart blanks without redraw when pointer >1 slot away) — out of scope.
- `--danger` used as confetti fill (non-text, AA-exempt like `--gold`).
- Backlog: mascot personality pass + dark mode remain future items (`docs/backlog.md`).
