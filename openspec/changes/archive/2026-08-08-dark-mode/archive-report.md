# Archive Report: dark-mode

**Change**: dark-mode (per-user theme preference, token-first dark theme)
**Status**: COMPLETE · **Verdict**: PASS (verify-report.md, orchestrator-inline)
**Archived**: 2026-08-08 · **Merged**: PRs #34 → #35 (merge commit `ea6ac49`)

## Final State

- Both stacked PRs merged to main in order, CI-green at merge time (browser-smoke + test; fresh merge refs via update-branch).
- Service restarted; dark mode live (stamp `ea6ac49`).
- Test totals at close: **378 pytest** (baseline 361 + 17) · **96 node:test** (93 + 3) · pyright **0 errors** · smoke **34/34** (real Chromium: Appearance radio, toggle→dark, system-follow).
- Specs synced: `openspec/specs/theme-preference/spec.md` (new capability, full spec); `game-appearance` and `weight-tracking` extended additively with the dark-mode requirements.

## What Shipped

1. **Backend (PR #34)**: per-user `theme` key ("system"|"light"|"dark", default "system") through the settings plumbing; `_valid_theme` (422 outside); onboarding rejects the key; `[data-theme="dark"]` token block (pinned dark palette, lightened accent-dark/danger for AA, `--accent` constant `#2f7d54` — lockstep/mascot/manifest safe); toast tokenized.
2. **Frontend (PR #35)**: `resolveTheme` pure helper (truth-table tested), FOUC-safe inline head script, `applyTheme` + server-wins in loadData, matchMedia listener only in system mode, header 🌙 toggle + Settings Appearance radio, `refreshChartColors()` (token-sourced, no hex literals, redraw visible charts).

## Follow-ups (non-blocking)

- gga strict-mode 30-line verdict window flake persists (documented; consider project `.gga` `STRICT_MODE=false`).
- Pre-existing chart-tooltip hover quirk (drawChart blanks >1 slot away) — still open.
- Next backlog items: mascot personality pass, checkpoint celebration notifications, gamified goals dashboard.
