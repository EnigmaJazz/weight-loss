# Proposal: Dark Mode

## Intent

The token-driven SPA only offers a light theme. Users need a dark theme: user-selectable, defaulting to system preference, meeting WCAG AA on dark surfaces — without breaking palette-lockstep, SPA-gate, or smoke tests. Per-user isolation applies (config rule): the theme setting is per-account.

## Assumptions (product decisions)

1. Three-state preference `"system" | "light" | "dark"` (default `"system"`); system state follows `matchMedia(prefers-color-scheme)` live.
2. Header toggle (beside `#logout-btn`, visible pre-auth) + three-state radio in a new Settings "Appearance" card. Wizard untouched.
3. `[data-theme="dark"]` block after `:root` redefines `--bg --card --text --muted --accent-dark --border --danger --fox --gold --gold-deep` (bg `#0f172a`, card `#1e293b`, text `#e2e8f0`, muted `#94a3b8`, border `#334155`). `--accent` stays `#2f7d54` (lockstep/mascot/manifest safe). Never a bare `:root {` (gate regex); no media-variant theme-color meta.
4. Dark `--accent-dark` (≈`#58a97e`) and `--danger` lightened to WCAG AA on dark surfaces.
5. Toast tokenized (`--toast-bg`/`--toast-text`): hardcoded `rgba(15,23,42,.92)` bg is invisible on dark.
6. Charts: keep `CHART_COLORS` identifier; add `refreshChartColors()` mutating the same object from tokens (no hex literals in app.js); theme hook redraws visible charts. `CHART_FONT` unchanged.
7. Per-user `theme` key via existing plumbing (`DEFAULT_SETTINGS`, `AppSettings.theme`, `_settings_from_conn`, `SettingsIn` + `_valid_theme` mirroring `_valid_weight_display`); PUT/GET round-trip; invalid → 422; `OnboardingIn` untouched.
8. FOUC-safe pre-auth: inline `<head>` script sets `dataset.theme` from localStorage with matchMedia fallback; server setting wins post-login (`loadData`); manual toggle writes localStorage.
9. `resolveTheme(pref, systemPref)` pure helper in format.js (UMD) + node:test.
10. Gates: API round-trip + 422 (test_api.py); `theme.test.mjs`; test_spa_gate.py pins dark block selector/colors + toggle wiring; smoke adds toggle + `data-theme` assertion; palette-lockstep stays green.
11. Manifest/meta `theme_color` stay `#2f7d54`.

## Scope

### In Scope
- Dark token block + toast tokenization + AA contrast values (style.css)
- Theme lifecycle: header toggle, Settings card, persistence, FOUC script, matchMedia listener
- `refreshChartColors()` + `resolveTheme()` + tests/gates

### Out of Scope
- Wizard theme step; `@media (prefers-color-scheme)` CSS block (JS is single source of truth)
- Manifest `background_color`/`theme_color` or meta changes; palette customization; per-widget theming

## Capabilities

### New Capabilities
- `theme-preference`: three-state preference lifecycle, live system-follow, per-user persistence, toggle UX, FOUC-safe pre-auth theming, `resolveTheme`

### Modified Capabilities
- `game-appearance`: dark `[data-theme="dark"]` token block (accent constant), toast tokenization, AA dark contrast, chart color refresh
- `weight-tracking`: Settings Contract accepts/round-trips `theme`; invalid values → 422

## Approach

Exploration Approach 1: token-first override + settings-plumbed theme. No CSS `prefers-color-scheme` block — JS is the single source of truth (inline script + `resolveTheme` + matchMedia change listener, active only in "system" mode) setting `data-theme` on `<html>`; light is the no-JS default. Inline head script avoids a new stamped asset.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `static/style.css` | Modified | Dark block, toast tokens, AA values |
| `static/app.js` | Modified | Toggle, Appearance radio, `applyTheme`, `refreshChartColors` |
| `static/format.js` | Modified | `resolveTheme` helper |
| `static/index.html` | Modified | Header toggle, Appearance card, FOUC script |
| `constants.py` / `models.py` / `database.py` / `routes.py` | Modified | `theme` key plumbing + validation |
| `tests/*`, `tests/smoke-ui.sh` | Modified | New gates + smoke step |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Gate regex collisions (dark selector, app.js hex literals) | Med | Pin tests; selector `[data-theme="dark"]`; tokens only |
| AA contrast on dark surfaces | Med | Design-phase verification of palette values |
| Chart colors stale after theme change | Low | Keep `CHART_COLORS`; refresh + redraw hook |
| FOUC pre-auth | Low | Inline pre-paint script; no-store index |

## Rollback Plan

`git revert` of the change commit. `theme` key is additive (missing row → default `"system"`); no schema migration; old clients unaffected.

## Dependencies

None — no new packages or external assets; key/value settings table needs no migration.

## Success Criteria

- [ ] pytest, node:test, smoke-ui.sh all green incl. new theme tests
- [ ] Theme round-trips via GET/PUT `/api/settings`; invalid value → 422
- [ ] `data-theme` flips live with system change; no FOUC; dark palette meets AA

## Open Questions

- Header button behavior: cycle 3 states vs quick light/dark flip
- Manifest `background_color` (`#f5f7fa` keep vs neutral) — `theme_color` fixed
- Exact dark palette values (design phase; AA-gated)
