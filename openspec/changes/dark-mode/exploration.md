# Exploration: Dark Mode

Status: success. Change: `dark-mode`. Store: OpenSpec. Explored: token inventory, chart
token caching, theme persistence/UX, gates, prefers-color-scheme flow.

## Current State

The SPA is fully token-driven after `game-appearance` (merged f1ec104). `static/style.css`
`:root` declares 24 tokens. Semantic color tokens (`--bg #f5f7fa`, `--card #ffffff`,
`--text #1f2933`, `--muted #6b7280`, `--accent #2f7d54`, `--accent-dark #266442`,
`--border #e2e8f0`, `--danger #c0392b`, `--fox #eb892c`, `--fox-dark`, `--gold`, `--gold-deep`)
plus scale tokens (`--radius-*`, `--shadow-*`, `--space-*`, `--font-*`). Every rule consumes
tokens; tints use `color-mix(in srgb, var(--accent|--danger) X%, var(--card))`; confetti fills
from inline `var(--color)` with `var(--fox|--gold|--accent|--danger)` — all re-theme
automatically when the semantic tokens change.

Charts read tokens ONCE at module scope (`static/app.js` ~L1064): `CHART_COLORS` (line
`--accent`, grid `--border`, muted `--muted`, tooltip `--text`, tooltipText `--card`) and
`CHART_FONT`. Draws happen in `loadData()` and in `switchTab("progress")` on visibility.

Settings are a per-user key/value table (`settings(user_id, key, value)`), no schema
migration needed for new keys: `DEFAULT_SETTINGS` (constants.py L29), `SettingsIn`
(routes.py L351, `extra="forbid"`), `AppSettings` (models.py L121), `_settings_from_conn`
(database.py L849) defaults missing rows. `_apply_settings` upserts; `null` restores default.
Frontend pure helpers live in `static/format.js` (UMD), node:test in `tests/frontend/*.test.mjs`
imports the REAL format.js.

Auth/onboarding screens render before login; `index.html` is fully static, stamped at
startup (`main.py _stamped_index_html`, `Cache-Control: no-store`). `prefers-reduced-motion`
already uses `matchMedia` (app.js confetti gate) — precedent for `prefers-color-scheme`.

## Token inventory — dark coverage

Redefining these 10 semantic tokens in a `[data-theme="dark"]` block covers the whole UI:
`--bg --card --text --muted --accent-dark --border --danger --fox --gold --gold-deep`
(`--accent` intentionally UNCHANGED — see Risks/gates). Scale tokens and fonts unchanged.

Non-token colors needing explicit handling:

| Location | Value | Dark issue |
|---|---|---|
| `.toast` (style.css L535) | `rgba(15,23,42,.92)` + `#f8fafc` | toast bg ≈ proposed dark `--bg` → invisible; needs `--toast-bg/--toast-text` tokens or a dark override (e.g. lighter surface + border) |
| `.card` box-shadow (L159) | `0 1px 3px rgba(0,0,0,.05)` | duplicates `--shadow-1` (currently UNUSED token); cosmetic — switch to `var(--shadow-1)` for themeability |
| header/button `#fff` (L63, L216) | on `--accent` | fine in both themes (accent constant) |
| inline fox SVG (index.html favicon + mascot) | rect `#2f7d54`, art `#eb892c/#b45c16/#fcf8f0/#26201e` | rect == `--accent`; artwork cream/ink reads on both themes → zero changes IF accent stays constant |
| `--shadow-1/2/3`, `--gold`, `--gold-deep`, `--fox-dark`, `--space-1`, `--space-5`, `--radius-lg` | declared, 0 usages | no dark work needed |

Dark contrast notes (design-phase input): `--accent-dark #266442` fails AA on a dark card
(≈2.1:1) → lighten in dark (e.g. `#58a97e` ≈5.1:1); `--danger #c0392b` ≈2.7:1 on dark card
→ lighten for text uses (`.error`, `.entry-delete`); `--muted` → e.g. `#94a3b8`; `--text` →
e.g. `#e2e8f0`. Candidate dark palette: `--bg #0f172a`, `--card #1e293b`, `--border #334155`.

## Chart token caching — re-theme path

`CHART_COLORS` is a module-scope `const` read once (L1064-1074); a theme change leaves
canvases painted with stale colors and re-draws would use stale values. Cleanest path that
keeps the gate green (gate pins substring `CHART_COLORS`, `CHART_FONT`, `getComputedStyle`
and forbids chart hex literals in app.js): keep the identifier, add
`refreshChartColors()` that re-reads computed styles into the same object (const object,
mutable props); call it from the theme hook, then redraw the three charts when the Progress
panel is visible (`!$("tab-progress").hidden`). `CHART_FONT` needs no refresh (font-family is
theme-independent). Alternative (per-draw getter) is cleaner but renames the constant →
gate change required.

Theme hook: `applyTheme(resolved)` — sets `document.documentElement.dataset.theme`, calls
`refreshChartColors()`, redraws visible charts, optionally persists. Wired from the toggle
handler, `loadData()` (server setting), the `matchMedia("(prefers-color-scheme: dark)")`
change listener (only while pref is "system"), and the FOUC inline script.

## Theme preference UX + persistence

Rides existing settings plumbing end-to-end. New `theme` key: `"system" | "light" | "dark"`,
default `"system"`. Touch points:

- `constants.py` `DEFAULT_SETTINGS` → `"theme": "system"`
- `routes.py` `SettingsIn` + a `_valid_theme` validator (422 on bad values) — pattern
  mirrors `_valid_weight_display`; `OnboardingIn` untouched (wizard has no theme step)
- `models.py` `AppSettings.theme: str = "system"`
- `database.py` `_settings_from_conn` → `theme=str(stored.get("theme", DEFAULT_SETTINGS["theme"]))`
- `static/app.js` `renderSettings` (L1371) sets the Appearance radio; a debounced PUT like
  `saveUnitPreference` (L1729) or the settings save handlers persist `{theme}`
- `static/format.js` new pure `resolveTheme(pref, systemPref) -> "light"|"dark"` (testable
  via node:test, like `shouldCelebrate`)
- `static/index.html` new "Appearance" card in the Settings tab + a header quick-toggle;
  inline FOUC script in `<head>` (see below)

Pre-auth theming (auth/onboarding screens, no user yet): localStorage fallback read by an
inline `<head>` script BEFORE first paint (`document.documentElement.dataset.theme`), with
`matchMedia("(prefers-color-scheme: dark)")` as the default. Post-login the server setting
wins in `loadData()`; manual toggles write through to localStorage too so the auth screen
matches the user's last choice. The inline script is a minimal 3-line duplication of
`resolveTheme` — a gate test can pin that it exists (localStorage + matchMedia references).

Toggle placement: header button (next to `#logout-btn`, `margin-left: auto` keeps logout
pinned) is always visible incl. pre-auth screens; three-state radio (System/Light/Dark) in a
new Settings "Appearance" card is the canonical persistence surface. `showTracker()`/
`showAuthScreen()` are unaffected — the header renders in all states.

## Gates at risk

- `tests/test_palette_lockstep.py` — parses FIRST `--accent:` match; safe if `:root` keeps
  `#2f7d54` and the dark block comes after `:root`. Keep `--accent` constant → test untouched.
  The HTML regex requires `name="theme-color"` IMMEDIATELY followed by `content=` — do NOT add
  a `<meta name="theme-color" media="...">` variant (breaks `_accent_from_html`); keep the
  single static meta at `#2f7d54`.
- `tests/test_spa_gate.py`:
  - `_root_block` regex `:root\s*\{([^}]*)\}` — dark block must NOT be a bare `:root {`
    selector (use `[data-theme="dark"]` or `:root[data-theme="dark"]`); tokens must stay in `:root`
  - `test_app_js_drives_chart_colors_from_tokens` — keep `CHART_COLORS`/`CHART_FONT`/
    `getComputedStyle` strings; NEVER add `#94a3b8`, `#e2e8f0`, `#f8fafc`, `rgba(15, 23, 42`
    literals to app.js (dark chart colors must come from tokens)
  - `test_manifest_theme_color_stays_brand_accent` — manifest unchanged → green
  - `test_asset_tuples_carry_cache_stamps` — no new external assets (inline head script +
    existing stamped style.css) → green; if a separate `theme.js` is introduced instead, it
    MUST join `main.py _JS_SCRIPTS` + the gate `_STAMPED_ASSETS`
- `tests/smoke-ui.sh` — text pins unchanged; ADD: toggle selector step + dark-mode step
  (assert `document.documentElement.dataset.theme === "dark"` via the existing `--raw eval`
  pattern, e.g. `playwright-cli --raw eval 'document.documentElement.dataset.theme'`)
- `static/manifest.webmanifest` — `theme_color #2f7d54` unchanged; `background_color #f5f7fa`
  (light splash) can stay or move to a neutral — decide in proposal
- New tests: `tests/test_api.py` theme round-trip + 422 rejection (mirror the unit-preference
  parametrized tests L130-156); `tests/frontend/theme.test.mjs` for `resolveTheme`
- `tests/test_onboarding.py` — untouched (no theme key in OnboardingIn)

## prefers-color-scheme flow

JS-driven single source of truth: the inline head script + `resolveTheme()` + the matchMedia
change listener all set `data-theme` on `<html>`; CSS has NO `@media (prefers-color-scheme)`
theme block (avoids two-source drift, matches the reduced-motion precedent of JS matchMedia
gates). Light is the no-JS default. `data-theme` is set pre-paint by the inline script, so
no FOUC. index.html is `Cache-Control: no-store` — inline script changes propagate instantly.

## Approaches

1. **Token-first CSS override + settings-plumbed theme (recommended)** — `[data-theme="dark"]`
   block redefining the 10 semantic tokens (accent constant), toast tokenization, `theme`
   settings key through existing plumbing, `resolveTheme` in format.js, FOUC inline script,
   header toggle + Settings radio, `refreshChartColors()` + redraw hook, matchMedia listener.
   - Pros: token-first covers ~100% of the UI; accent constant keeps lockstep + mascot/
     manifest/meta green; settings plumbing is additive (key/value table, no migration);
     testable pure helper; no new stamped assets
   - Cons: 3-state toggle is more UI than a binary flip; toast needs explicit handling
   - Effort: Low-Medium
2. **CSS `@media (prefers-color-scheme)` only, no setting** — pure media query dark theme.
   - Pros: zero backend work, zero JS
   - Cons: no per-user override, no persistence, can't honor a user's explicit choice vs
     their OS; contradictsthe backlog ("Dark mode under Appearance" implies a setting)
   - Effort: Low
3. **Per-draw chart color getter** — replace `CHART_COLORS` const with a function.
   - Pros: no refresh bookkeeping
   - Cons: renames the pinned identifier → test_spa_gate.py change required; tooltip
     mousemove re-reads computed styles per move
   - Effort: Low (but gate churn)

## Recommendation

Approach 1. Keep `--accent: #2f7d54` constant across themes (brand anchor; keeps the
four-location lockstep, manifest, meta theme-color, mascot art, and header/button white-text
all valid with zero changes). Redefine the 9 other semantic colors + lighten `--accent-dark`
and `--danger` for AA on dark surfaces; tokenize the toast. Persist `theme` via the existing
settings key/value plumbing with `"system"` default. `resolveTheme` in format.js + node:test;
FOUC inline head script (localStorage + matchMedia); header toggle + Settings radio;
`refreshChartColors()` + redraw when Progress is visible; matchMedia change listener only in
"system" mode. Extend smoke-ui.sh with a toggle + `data-theme` assertion; add API theme
round-trip/422 tests.

## Risks

- 3-state vs 2-state toggle (System/Light/Dark vs Light/Dark) — recommend 3-state; header
  toggle cycles or opens the setting
- Where the toggle lives (header vs Settings vs both) — recommend both; Settings-only leaves
  pre-auth users unable to change
- Whether "system" is the default — recommend yes (`DEFAULT_SETTINGS` + localStorage
  absence → system)
- theme_color / meta / manifest: keep all static `#2f7d54` (lockstep + spec); do NOT add a
  media-variant meta (breaks `_accent_from_html`). Runtime JS meta update is unnecessary —
  the header stays green in both themes
- Auth-screen theming: localStorage fallback pre-auth; server wins post-login; write-through
  on manual toggle
- Wizard: no theme step in v1 (scope guard); theme follows system until changed in Settings
- AA contrast in dark for `--accent-dark`/`--danger`/`--muted` text uses — design phase must
  pick values that pass (design rule: new palette colors MUST meet WCAG AA)
- `.toast` invisible-on-dark — must be tokenized or overridden, not left as-is
- Gate pin `CHART_COLORS` identifier must survive the refresh refactor

## Ready for Proposal

Yes. Tell the user: dark mode is a token-first change with additive settings plumbing; the
only real decisions are (a) 3-state toggle confirmed, (b) header + Settings placement
confirmed, (c) system default confirmed, (d) manifest/meta/theme_color stay `#2f7d54`
(lockstep) — all four can be resolved in the proposal without further exploration.
