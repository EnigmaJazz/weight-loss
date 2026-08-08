# Tasks: Dark Mode

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | S1 ~140–170, S2 ~180–220, total ~320–390 |
| 400-line budget risk | Medium (total); Low per slice |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 backend+CSS → PR 2 JS lifecycle+UX |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test | Runtime harness | Rollback |
|------|------|-----------|--------------|-----------------|----------|
| 1 | theme backend + dark CSS | PR 1 | `pytest -q -k theme tests/test_api.py && pytest -q tests/test_spa_gate.py tests/test_palette_lockstep.py` | conftest API + gates; browser N/A (no JS) | revert backend + CSS; light intact |
| 2 | JS lifecycle + UX | PR 2 | `node --test tests/frontend/theme.test.mjs && pytest -q tests/test_spa_gate.py && tests/smoke-ui.sh` | smoke toggle → `data-theme` assert | revert app/format/index + asserts |

**Gate landmines**: dark block MUST be `[data-theme="dark"]` — never bare `:root {` (`_root_block` regex). No `media=` theme-color meta. No dark hex in app.js (extend L395 ban).

## Phase 1: S1 Backend RED (PR 1)

- [x] 1.1 `tests/test_api.py`: GET settings defaults `theme=="system"` (mirror `test_settings_unit_defaults`).
- [x] 1.2 `tests/test_api.py`: roundtrip parametrized dark/light/system, PUT→GET exact (L130 pattern).
- [x] 1.3 `tests/test_api.py`: invalid `auto`/`purple` → 422, settings unchanged.
- [x] 1.4 `tests/test_api.py`: theme `null` → `"system"`; per-user isolation A=dark/B=system; onboarding rejects `theme`.

## Phase 2: S1 Backend GREEN (PR 1)

- [x] 2.1 `constants.py`: add `"theme": "system"` to `DEFAULT_SETTINGS`.
- [x] 2.2 `models.py`: add `theme: str = "system"` to `AppSettings`.
- [x] 2.3 `database.py`: `_settings_from_conn` maps `theme` with default fallback.
- [x] 2.4 `routes.py`: `_valid_theme` + `SettingsIn.theme` + `@field_validator`; `OnboardingIn` untouched (extra=forbid); `asdict` round-trips.

## Phase 3: S1 CSS foundation (PR 1)

- [x] 3.1 `tests/test_spa_gate.py`: `[data-theme="dark"]` block declares `--bg #0f172a`, `--card #1e293b`, `--text #e2e8f0`, `--muted #94a3b8`, `--border #334155`, `--accent-dark #58a97e`, `--danger`, `--fox`/`--gold`/`--gold-deep`, `--toast-bg`/`--toast-text`.
- [x] 3.2 `tests/test_spa_gate.py`: exactly one `:root\s*\{` match; no `media=` meta; `.toast` uses `var(--toast-*)`, no `rgba(15,23,42`.
- [x] 3.3 `static/style.css` GREEN: dark block after `:root` (L43), `--accent` NOT redeclared; `:root` toast tokens; `.toast` L535 var swap; `.card` shadow → `var(--shadow-1)`; reduced-motion-gated transition.
- [x] 3.4 Verify: theme+gate+lockstep green (S1 shippable).

## Phase 4: S2 JS RED (PR 2)

- [x] 4.1 `tests/frontend/theme.test.mjs`: `resolveTheme` truth table — (system,dark)→dark, (system,light)→light, (light,*)→light, (dark,*)→dark, (system,null)→light.
- [x] 4.2 `tests/test_spa_gate.py`: app.js has `applyTheme`+`refreshChartColors`+`prefers-color-scheme` matchMedia; HTML has `#theme-toggle`, `name="appearance"` radio, FOUC head script; no dark hex in app.js.

## Phase 5: S2 JS GREEN (PR 2)

- [x] 5.1 `static/format.js`: `resolveTheme(pref, systemPref)` in `api` UMD export.
- [x] 5.2 `static/app.js`: `refreshChartColors()` mutates `CHART_COLORS` via `getComputedStyle`; `applyTheme` sets `dataset.theme`+localStorage, redraw when `!$("tab-progress").hidden`.
- [x] 5.3 `static/app.js`: `loadData` applies server theme (wins); matchMedia listener only in system mode (D5).
- [x] 5.4 `static/app.js`: toggle cycles system→light→dark→system + PUT; `renderSettings` Appearance radio mirrors `setRadio("weight-display")` L1385.
- [x] 5.5 `static/index.html`: `#theme-toggle` before `#logout-btn` (always visible); Appearance card; FOUC `<head>` script — localStorage → matchMedia → `dataset.theme` (light no-JS default).

## Phase 6: S2 Smoke + verify (PR 2)

- [x] 6.1 `tests/smoke-ui.sh`: click `#theme-toggle` → eval `dataset.theme` == "dark" → click → "light" (selector-only, no text pins).
- [x] 6.2 Full pytest + `node --test tests/frontend/theme.test.mjs` + `tests/smoke-ui.sh` green.
