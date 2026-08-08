# Verify Report: dark-mode

**Change**: dark-mode · **Branch**: feat/dark-mode-s2 (2 slices, 5 commits, tip `f207480`)
**Verdict**: PASS · **Method**: orchestrator-inline verification (delegated verify agents have been unreliable this session; suites re-run directly against live evidence)

## Suite Evidence (raw, re-run by orchestrator)

| Gate | Result |
|---|---|
| `.venv/bin/python -m pytest -q` | **378 passed** (baseline 361 + 17) |
| `node --test tests/frontend/*.test.mjs` | **96 pass / 0 fail** (baseline 93 + 3 resolveTheme cases) |
| `.venv/bin/pyright` | **0 errors, 0 warnings** |
| `tests/smoke-ui.sh` (scratch server, real Chromium) | **34 passed / 0 failed** — Appearance radio, toggle→dark, system-follow round-trip (slice-2 run) |

## Requirements Coverage (spec → implementation → test → PASS)

| Spec requirement | Implementation | Test | Result |
|---|---|---|---|
| Three-State Theme Preference | `theme` settings key ("system"\|"light"\|"dark", default "system"); `_valid_theme` validator (422 outside); per-user isolated; OnboardingIn rejects theme (extra=forbid) | `test_api.py` 8 tests (default/roundtrip×3/422×2/null/isolation) + `test_onboarding.py` rejects-theme | ✅ |
| Dark Token Block | `[data-theme="dark"]` block after :root with pinned values (--bg #0f172a, --card #1e293b, --text #e2e8f0, --muted #94a3b8, --border #334155, --accent-dark #58a97e, --danger #f06a5d, --fox #f5a850, --gold #fbd34a); --accent constant #2f7d54 (NOT redeclared); no bare `:root {`; no media-variant theme-color meta | `test_spa_gate.py` 4 gate tests (12 tokens, single-`:root` count, no media meta, toast tokens) + `test_palette_lockstep.py` green | ✅ |
| Toast Tokenization | `--toast-bg`/`--toast-text` in :root + dark overrides; `.toast` consumes vars | gate asserts + visual smoke | ✅ |
| Dark Chart Color Refresh | `refreshChartColors()` mutates the pinned `CHART_COLORS` object via getComputedStyle; redraw when progress tab visible; no hex literals in app.js (gate hex ban incl. dark palette) | `test_spa_gate.py` wiring + app.js hex-ban gates; smoke chart render | ✅ |
| Theme Lifecycle / FOUC | inline <head> script (try/catch localStorage → matchMedia fallback → data-theme pre-paint, value-validated); loadData server-wins; `applyTheme` writes dataset+localStorage+refresh; matchMedia listener only in "system" mode (stored handler ref); header toggle (🌙) + Settings Appearance radio (debounced PUT) | `test_spa_gate.py` FOUC/toggle/radio gates; smoke radio→toggle→system round-trip | ✅ |
| resolveTheme pure helper | `resolveTheme(pref, systemPref)` in format.js UMD (invalid pref → system resolution; null systemPref handled) | `tests/frontend/theme.test.mjs` (3 tests, 7-pair truth table + invalid + null) | ✅ |
| Gates non-regression | palette lockstep green; gate suite green; smoke text pins unchanged (+3 theme steps); node suite green | full runs above | ✅ |

## Live Spot-Check Evidence

- Slice-2 smoke (real Chromium, scratch server port 8128): Appearance radio → Light; header toggle → `data-theme="dark"` asserted; toggle → System resolved against the browser's live `matchMedia`; all 31 pre-existing steps still pass.
- The E2E layer caught a real defect the static gates could not (resolveTheme not destructured from WeightFormat in app.js → ReferenceError killing loadData; fixed in the same slice, smoke 34/34 after).

## Findings

- **CRITICAL**: none · **WARNING**: none
- **SUGGESTION**: (1) one design deviation — FOUC script is defensive (try/catch + value validation) beyond the design's bare localStorage read, strictly an improvement; (2) `margin-left: auto` moved from `#logout-btn` to `#theme-toggle` per design D4 (required one-line style.css touch in slice 2); (3) pre-existing chart-tooltip hover quirk still open (out of scope).

## Verdict

**PASS** — all 3 specs' requirements implemented and covered by passing gates; suites re-run by the orchestrator; browser smoke proves the toggle, dark theme application, and system-follow live. Rollback: revert the 5 commits / remove the dark block + theme key (additive, no migration).
