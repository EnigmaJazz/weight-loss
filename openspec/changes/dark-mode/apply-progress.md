# Apply Progress — dark-mode (Slice 1 + Slice 2 / PR 1 + PR 2 — COMPLETE)

- **Date**: 2026-08-08
- **Mode**: Strict TDD (`strict_tdd: true`, pytest + node:test + smoke-ui.sh runners)
- **Artifact store**: OpenSpec (+ Engram)
- **Slices**: 1 of 2 (Phases 1–3, backend + CSS dark foundation) + 2 of 2 (Phases 4–6, JS lifecycle + UX) — both applied
- **Chain**: auto-chain / stacked-to-main, branch `feat/dark-mode-s1` (slice 1, from `main` @ `9873cef`), branch `feat/dark-mode-s2` (slice 2, from slice-1 tip `d416193`)
- **Status**: 22/22 tasks complete (tasks 1.1–6.2) — dark-mode fully implemented, ready for verify

## Scope Boundary

- **Slice 1 (PR 1)**: `theme` settings key (backend), `[data-theme="dark"]` CSS block + toast tokenization.
- **Slice 2 (PR 2)**: JS lifecycle (`resolveTheme`, `applyTheme`, `refreshChartColors`), toggle/radio UX, FOUC head script, `smoke-ui.sh` theme-toggle step.
- **Out of scope**: nothing remains — all phases implemented.

## Commits

### Slice 1 (feat/dark-mode-s1)

| Hash | Subject | Files |
|------|---------|-------|
| `78514e6` | `feat(settings): add per-user theme preference (system\|light\|dark)` | constants.py, models.py, database.py, routes.py, tests/test_api.py, tests/test_onboarding.py |
| `d416193` | `feat(style): dark theme token block and toast tokenization` | static/style.css, tests/test_spa_gate.py |

### Slice 2 (feat/dark-mode-s2)

| Hash | Subject | Files |
|------|---------|-------|
| `bbf8c94` | `feat(theme): add pure resolveTheme helper with truth-table tests` | static/format.js, tests/frontend/theme.test.mjs |
| `0948a0d` | `feat(theme): wire JS theming lifecycle — FOUC, toggle, appearance radio` | static/app.js, static/index.html, static/style.css, tests/test_spa_gate.py, tests/smoke-ui.sh |

All four passed the `gga` pre-commit review gate (AGENTS.md rules). Neither branch pushed; no PR opened (per delivery context).

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 GET default `theme=="system"` | tests/test_api.py | Integration | ✅ 94/94 | ✅ Written | ✅ Passed | ➖ Single (defaults have one value) | ✅ Clean |
| 1.2 Round-trip dark/light/system | tests/test_api.py | Integration | ✅ 94/94 | ✅ Written | ✅ Passed | ✅ 3 cases (parametrized) | ✅ Clean |
| 1.3 Invalid `auto`/`purple` → 422, unchanged | tests/test_api.py | Integration | ✅ 94/94 | ✅ Written | ✅ Passed | ✅ 2 cases + unchanged-assert | ✅ Clean |
| 1.4 null→system, isolation, onboarding rejects theme | tests/test_api.py + tests/test_onboarding.py | Integration | ✅ 94/94 | ✅ Written (8 failed) | ✅ Passed | ✅ 3 cases (null / pair / extra-forbid guard) | ✅ Clean |
| 2.1 DEFAULT_SETTINGS theme | constants.py | Unit (config) | ✅ 94/94 | ✅ (driven by 1.1–1.4 RED) | ✅ Passed | ➖ Structural — one possible output | ➖ None needed |
| 2.2 AppSettings.theme | models.py | Unit (dataclass) | ✅ 94/94 | ✅ (driven by 1.1–1.4 RED) | ✅ Passed | ➖ Structural — one possible output | ➖ None needed |
| 2.3 `_settings_from_conn` theme map | database.py | Unit | ✅ 94/94 | ✅ (driven by 1.1–1.4 RED) | ✅ Passed | ➖ Single (mirrors existing key pattern) | ✅ Clean |
| 2.4 `_valid_theme` + SettingsIn validator | routes.py | Integration | ✅ 94/94 | ✅ (driven by 1.1–1.4 RED) | ✅ Passed | ✅ 3 states + 2 rejects | ✅ Clean |
| 3.1 dark block pinned tokens | tests/test_spa_gate.py | Static gate | ✅ 94/94 | ✅ Written (failed) | ✅ Passed | ✅ 12 tokens asserted (full set) | ✅ Clean |
| 3.2 single `:root {`, no media meta, toast tokens | tests/test_spa_gate.py | Static gate | ✅ 94/94 | ✅ Written (2 failed) | ✅ Passed | ✅ 4 assertions (selector count / meta / root / toast body) | ✅ Clean (fixed docstring escape) |
| 3.3 style.css dark block + toast vars | static/style.css | Static gate | ✅ 94/94 | ✅ (driven by 3.1–3.2 RED) | ✅ Passed | ➖ Single — values pinned by design | ✅ Clean |
| 3.4 Verify theme+gate+lockstep green | — | — | ✅ 94/94 | n/a | ✅ Passed (97 passed focused; lockstep green) | ➖ Single | ✅ Clean |
| 4.1 resolveTheme truth table | tests/frontend/theme.test.mjs | Unit | ✅ 93/93 node | ✅ Written (3 failed: TypeError) | ✅ Passed 3/3 | ✅ 7-pair table + invalid-pref + null-systemPref (3 tests) | ✅ Clean |
| 4.2 SPA theme gates | tests/test_spa_gate.py | Static gate | ✅ 374/374 pytest | ✅ Written (4 failed) | ✅ Passed 25/25 | ✅ 4 gates (hooks / FOUC / toggle / radio) | ✅ Clean |
| 5.1 resolveTheme in UMD api | static/format.js | Unit | ✅ 93/93 | ✅ (driven by 4.1 RED) | ✅ Passed 3/3 | ✅ driven by 4.1's 3 tests | ✅ Clean |
| 5.2 refreshChartColors + applyTheme | static/app.js | Static gate + E2E | ✅ 374/374 | ✅ (driven by 4.2 RED) | ✅ Passed | ✅ getComputedStyle re-read all 5 tokens | ✅ Clean |
| 5.3 loadData server-wins + D5 listener | static/app.js | Static gate + E2E | ✅ 374/374 | ✅ (driven by 4.2 RED) | ✅ Passed | ✅ smoke: system-follow round-trip | ✅ Clean |
| 5.4 toggle cycle + Appearance radio | static/app.js + static/index.html | Static gate + E2E | ✅ 374/374 | ✅ (driven by 4.2 RED) | ✅ Passed | ✅ smoke: radio light → toggle dark → system | ✅ Clean |
| 5.5 FOUC script + toggle + Appearance card | static/index.html | Static gate | ✅ 374/374 | ✅ (driven by 4.2 RED) | ✅ Passed | ✅ 3 surfaces asserted | ✅ Clean |
| 6.1 smoke theme-toggle step | tests/smoke-ui.sh | E2E | ✅ 31-step baseline | ✅ Written (1 failed — caught real bug, see Issues) | ✅ Passed 34/34 | ✅ radio + toggle-dark + system-follow | ✅ Clean |
| 6.2 full verify | — | — | ✅ 374/374 | n/a | ✅ 378 pytest + 96 node + 34 smoke + pyright 0 | ➖ Single | ✅ Clean |

Triangulation notes:
- Task 5.1's pure-function RED was written before any production code (task 4.1); the format.js export is driven by that same failing test.
- Task 6.1's smoke step was the only E2E RED that caught a REAL bug (missing `resolveTheme` in the app.js WeightFormat destructure — see Issues), proving the smoke layer's value beyond the static gates.

## Work Unit Evidence

| Evidence | Required value |
|---|---|
| Focused test command and exact result | `node --test tests/frontend/theme.test.mjs` → **3 pass / 0 fail**; `.venv/bin/python -m pytest tests/test_spa_gate.py -q` → **25 passed in 0.27s** (21 baseline + 4 new) |
| Runtime harness command/scenario and exact result | `.venv/bin/python -m pytest -q` → **378 passed** (374 + 4 new gate); `node --test tests/frontend/*.test.mjs` → **96 pass / 0 fail** (93 + 3 new); `.venv/bin/pyright` → **0 errors, 0 warnings**; `tests/smoke-ui.sh http://localhost:8128` (scratch server, tmp DB/VAPID, real browser) → **34 passed, 0 failed** (31 baseline + 3 new theme steps) |
| Rollback boundary | `git revert` the two slice-2 commits on `feat/dark-mode-s2` (or reset to `d416193`): `git revert bbf8c94` + `git revert 0948a0d`. `theme` key is additive; FOUC script is inert without JS; light remains the no-JS default; slice-1 CSS/backend and all pre-change behavior are untouched by the revert. Never touches slice-1 commits. Slice-1 rollback (from previous progress): `git revert 78514e6` + `git revert d416193` (or reset branch to `9873cef`) — removes only slice-1 work, never touches PR-2 files (app.js, format.js, index.html, smoke-ui.sh untouched at that point). |

## Gate Landmines — Confirmed Safe

- ✅ **app.js hex ban**: `refreshChartColors()` re-reads tokens via `getComputedStyle` — no dark-palette hex literals added (`#94a3b8`, `#e2e8f0`, `#f8fafc`, `rgba(15, 23, 42` all still banned; gate `test_app_js_drives_chart_colors_from_tokens` green).
- ✅ **index.html**: FOUC bootstrap is a `<script>` in `<head>` (localStorage → matchMedia fallback → `dataset.theme`), NOT a media-variant `<meta name="theme-color">` (gate green).
- ✅ **Dark CSS block untouched in slice 2** except the one design-required D4 change: `margin-left: auto` moved from `#logout-btn` to `#theme-toggle` (design §JS Theming Lifecycle: "move margin-left:auto from #logout-btn to #theme-toggle" — this is the strictly-required style.css touch, reported per the gate landmine). The `[data-theme="dark"]` block itself was NOT modified.
- ✅ `--accent` NOT redeclared; `test_palette_lockstep.py` green.
- ✅ Slice-1 landmines (from previous progress): dark block selector is exactly `[data-theme="dark"]` — no `:root[data-theme...]`, no bare `:root {` (gate asserts `len(re.findall(r":root\s*\{", css)) == 1`); no `<meta name="theme-color" media=...>` variant; `--accent` NOT redeclared in the dark block; `tests/test_palette_lockstep.py` green — first `--accent` still `#2f7d54` in `:root`.

## Deviations from Design

1. **FOUC script try/catch**: design snippet reads `localStorage.getItem("theme")` directly; the shipped script wraps it in try/catch (storage can be blocked) and validates the value is exactly `"light"` or `"dark"` before trusting it — same behavior, defensive against storage exceptions. The gate test pins the localStorage read + matchMedia fallback + dataset.theme set, all present.
2. **Toggle icon**: design open question (🌙/☀ emoji vs SVG) resolved in apply — static 🌙 emoji, no new assets.
3. **D5 listener placement**: design says the matchMedia listener is "added in applyTheme when pref==='system', removed otherwise" — implemented as `syncThemeSystemListener()` called from `applyTheme`, keyed on the module `themePref` state, with a stored handler ref so add/remove target the identical function.
4. **smoke toggle assertions**: tasks 6.1 said "click → dark → click → light"; the design's toggle cycle is system→light→dark→system, so the smoke pins the pref to Light via the Appearance radio first (deterministic), then asserts toggle → dark, then toggle → system-resolved theme (asserted against the browser's live `matchMedia` result, not a hardcoded light). This also exercises the Appearance radio in-browser.
5. **Slice-1 note (from previous progress)**: the onboarding-rejects-theme test was placed in `tests/test_onboarding.py` (where the `_payload` + extra-forbid pattern lives, per design Testing Strategy) rather than in `test_api.py`; tasks.md 1.4 lists it under `test_api.py` but the design's Testing Strategy row explicitly maps it to test_onboarding.py.

## Issues Found

1. **Missing `resolveTheme` in app.js destructure (caught by smoke RED, fixed before commit)**: the first smoke run failed the toggle step with data-theme stuck at "light". Root cause: `resolveTheme` was not in the `const { ... } = globalThis.WeightFormat;` destructure at app.js module scope — every `resolveTheme(...)` call threw `ReferenceError`, which (a) killed `loadData` before `renderStreaks` (flame count 0) and (b) aborted the toggle handler before `applyTheme`. The radio assertion had passed trivially because the theme was already light. Fixed by adding `resolveTheme` to the destructure; smoke then passed 34/34. This is why the E2E smoke layer exists beyond the static gates — the gate tests only assert string presence.
2. **`gga` pre-commit gate**: no issues this slice; both commits passed first try.
3. **Slice-1 notes (from previous progress)**: `gga` gate blocked commit 1 on 3 pre-existing type-hint violations in test helpers (fixed with one-line annotations); a `gga` strict-mode glitch on commit 2 retry (provider output past the 30-line parse window) resolved by retrying the identical commit; commit 1 review flagged a redundant `_valid_date` re-import (routes.py:194) as non-blocking — left untouched.

## Remaining Tasks

None — 22/22 tasks complete. Next phase: `sdd-verify`.

## Workload / PR Boundary

- Mode: **stacked PR slice** (slice 2 of 2, auto-chain / stacked-to-main)
- Branch: `feat/dark-mode-s2` (targets `feat/dark-mode-s1` tip `d416193`; do NOT push / no PR opened)
- Boundary: starts at `d416193` (slice-1 tip), ends at `0948a0d` — JS theming lifecycle + UX only
- Review budget impact: slice 2 = 342 inserted / 4 deleted lines across 7 files (well under 400; forecast was ~180–220 but the smoke step + 4 gate tests + comments push it to ~340)
