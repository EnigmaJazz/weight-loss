# Design: Dark Mode

## Technical Approach

Token-first CSS override + additive `theme` settings key, JS as single source of truth. A `[data-theme="dark"]` block redefines the 10 semantic tokens (accent constant); `resolveTheme` + an inline FOUC head script + a matchMedia listener set `data-theme` on `<html>`; `refreshChartColors()` re-reads tokens into the existing `CHART_COLORS` object and redraws visible charts. Maps to specs `theme-preference` (lifecycle/UX), `game-appearance` (tokens/charts), `weight-tracking` (Settings contract).

## Architecture Decisions

| # | Decision | Option A | Option B | Choice | Why |
|---|----------|----------|----------|--------|-----|
| D1 | Dark block selector | `[data-theme="dark"]` | `:root[data-theme="dark"]` | A | Bare-stripped selector never collides with gate `_root_block` regex `:root\s*\{` |
| D2 | Chart refresh | Mutate `CHART_COLORS` in place | Per-draw getter | A | Keeps pinned identifier + `getComputedStyle` substring; gate stays green |
| D3 | Toggle in header | Always visible | Mirrors `#logout-btn` hidden state | Always visible | Spec: visible pre-auth; logout is hidden pre-auth |
| D4 | Right-group layout | `margin-left:auto` on toggle | Keep on `#logout-btn` | On toggle | Groups toggle+logout at flex-end |
| D5 | System follow | matchMedia listener only in `"system"` mode | Always-on listener | System-only | No reload drift; add/remove on pref change |

## Data Flow

```
localStorage ──┐
              ├→ inline <head> script (pre-paint) ──→ documentElement.dataset.theme
matchMedia ────┘                                            │
                                                            ▼
loadData() ──GET /api/settings──→ theme pref ──→ resolveTheme(pref, system)
      │                                                     │
      └── applyTheme(theme) ──→ dataset.theme + localStorage + refreshChartColors()
                                                    + redraw if #tab-progress visible
matchMedia change (system mode) ─────────────────────┘
toggle/radio ──→ applyTheme + PUT /api/settings + localStorage
```

## CSS (style.css)

Insert `[data-theme="dark"]` block AFTER `:root` (L43), BEFORE component rules. Token values:

```css
[data-theme="dark"] {
  --bg: #0f172a;
  --card: #1e293b;
  --text: #e2e8f0;
  --muted: #94a3b8;
  --accent-dark: #58a97e;   /* lightened from #266442 */
  --border: #334155;
  --danger: #f06a5d;        /* lightened from #c0392b */
  --fox: #f5a850;
  --gold: #fbd34a;
  --gold-deep: #e0b020;
  /* --accent UNCHANGED #2f7d54 (lockstep/mascot/manifest) */
  --toast-bg: #1e293b;
  --toast-text: #e2e8f0;
}
```
`--toast-bg`/`--toast-text` also declared in `:root` (`--toast-bg: rgba(15,23,42,.92); --toast-text: #f8fafc;`). `.toast` L535 swap: `background: var(--toast-bg); color: var(--toast-text);`. `.card` L159 box-shadow → `var(--shadow-1)`. Optional `transition: background-color .15s, color .15s` on `body`, gated `@media (prefers-reduced-motion: reduce){ ... transition: none }`.

**AA contrast (dark pairs, vs card #1e293b L≈0.0218):**

| Pair | Ratio | ≥4.5:1 |
|------|-------|--------|
| text `#e2e8f0`/card `#1e293b` | 11.9:1 | ✓ |
| text `#e2e8f0`/bg `#0f172a` | 14.5:1 | ✓ |
| muted `#94a3b8`/card | 5.7:1 | ✓ |
| accent-dark `#58a97e`/card | 5.2:1 | ✓ |
| danger `#f06a5d`/card | 4.8:1 | ✓ |

No `@media (prefers-color-scheme)` block; no media-variant `<meta theme-color>`.

## JS Theming Lifecycle (app.js + format.js + index.html)

format.js (UMD, add to `api`): `function resolveTheme(pref, systemPref){ if(pref==="dark")return"dark"; if(pref==="light")return"light"; return systemPref==="dark"?"dark":"light"; }` (nullable systemPref → light).

app.js `applyTheme(theme)`:
```js
function applyTheme(theme){
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("theme", theme);
  refreshChartColors();
  if(!$("tab-progress").hidden){ drawChart(chartData.weightEntries, chartData.weightSummary); drawExerciseChart(chartData.exerciseEntries); drawMealChart(chartData.mealEntries); }
}
```
Header toggle: `<button id="theme-toggle" type="button" class="secondary" aria-label="Toggle theme">🌙</button>` placed in `.header-row` right BEFORE `<button id="logout-btn">`. CSS: move `margin-left:auto` from `#logout-btn` to `#theme-toggle`. Toggle NOT hidden in `showAuthScreen`/`showOnboarding` (stays visible always); handler cycles system→light→dark→system and writes localStorage + PUT. Settings "Appearance" card: three-state radio `name="appearance"` (system/light/dark) added in `renderSettings` after the `weight-display` radio group (L1385), mirroring `setRadio` pattern; `change` → applyTheme + debounced `saveUnitPreference`-style PUT.

`loadData()` (after `await Promise.all`): `currentTheme = settings.theme || "system"; applyTheme(resolveTheme(currentTheme, systemPref()));` — server wins post-login. `prefers-color-scheme` change listener: stored handler ref; added in `applyTheme` when pref==="system", removed otherwise.

index.html `<head>` (after `<title>`, before `</head>`): FOUC inline script — `localStorage.getItem("theme")` → matchMedia fallback → `document.documentElement.dataset.theme=`. Light is no-JS default (no `data-theme` attr).

## Backend

- `constants.DEFAULT_SETTINGS += "theme": "system"`
- `models.AppSettings` += `theme: str = "system"`
- `database._settings_from_conn` += `theme=str(stored.get("theme", DEFAULT_SETTINGS["theme"]))`
- `routes._valid_theme(value)` mirrors `_valid_weight_display`: `if value is not None and value not in ("system","light","dark"): raise ValueError(...)`. `SettingsIn` += `theme: Optional[str] = None` + `@field_validator("theme") def validate_theme(cls,v): return _valid_theme(v)`. `OnboardingIn` untouched (extra="forbid" rejects `theme`). GET/PUT return `asdict(AppSettings)` — new key appears automatically; per-user isolation via `settings WHERE user_id=?`. `null` → DELETE row → default "system".

## Charts (app.js)

`refreshChartColors()` (module scope, after `CHART_COLORS`):
```js
function refreshChartColors(){
  const cs = getComputedStyle(document.documentElement);
  CHART_COLORS.line = cs.getPropertyValue("--accent").trim();
  CHART_COLORS.grid = cs.getPropertyValue("--border").trim();
  CHART_COLORS.muted = cs.getPropertyValue("--muted").trim();
  CHART_COLORS.tooltip = cs.getPropertyValue("--text").trim();
  CHART_COLORS.tooltipText = cs.getPropertyValue("--card").trim();
}
```
Same mutation target, no hex literals, `CHART_FONT` untouched. Called from `applyTheme`. Redraw: `drawChart`/`drawExerciseChart`/`drawMealChart` only when `!$("tab-progress").hidden`; hidden panel re-renders on next `switchTab("progress")`.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `static/style.css` | Modify | `[data-theme="dark"]` block (L43), `:root` toast tokens, `.toast` swap, `.card` shadow token, transition |
| `static/app.js` | Modify | `applyTheme`, `refreshChartColors`, toggle/radio handlers, `loadData` theme apply, matchMedia listener, renderSettings radio |
| `static/format.js` | Modify | `resolveTheme` + UMD export |
| `static/index.html` | Modify | `#theme-toggle` button, Appearance card/radios, FOUC head script |
| `constants.py` | Modify | `DEFAULT_SETTINGS["theme"]="system"` |
| `models.py` | Modify | `AppSettings.theme` |
| `database.py` | Modify | `_settings_from_conn` theme mapping |
| `routes.py` | Modify | `_valid_theme`, `SettingsIn.theme` field+validator |
| `tests/test_api.py` | Modify | theme round-trip 3 states + 422 + isolation (parametrized pattern) |
| `tests/frontend/theme.test.mjs` | Create | resolveTheme truth table (node:test) |
| `tests/test_spa_gate.py` | Modify | dark block presence+values, no bare `:root {`, no media-variant meta, toast tokens, `refreshChartColors` presence, no dark hex in app.js |
| `tests/smoke-ui.sh` | Modify | toggle click → `data-theme=dark` → back to light |

**Rollback:** `git revert` the change commit. `theme` key is additive; missing row → default `"system"`; no schema migration; old clients unaffected. Rollback boundary = the single change commit (all 12 files).

## Testing Strategy

| Layer | What | How |
|-------|------|-----|
| Unit | `resolveTheme` truth table (7 cases) | `tests/frontend/theme.test.mjs` (node:test, imports real format.js) |
| Integration | GET/PUT round-trip 3 states, 422 invalid (`auto`,`purple`), per-user isolation, onboarding rejects `theme` | test_api.py mirroring `test_settings_unit_roundtrip` parametrized pattern; test_onboarding.py extra-forbid |
| Static gate | dark block selector+values, no bare `:root {`, no media-variant meta, toast tokens, `refreshChartColors` present, no dark hex in app.js, `CHART_COLORS`/`CHART_FONT` survive | test_spa_gate.py additions; palette-lockstep unchanged (first `--accent` still #2f7d54) |
| E2E | toggle click flips `data-theme=dark`, back to light | smoke-ui.sh `--raw eval 'document.documentElement.dataset.theme'` |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No migration required. Additive settings key; CSS dark block is opt-in via `data-theme`; light remains the no-JS default; manifest/meta stay `#2f7d54`.

## Open Questions

- [ ] Header toggle icon (🌙/☀OK emoji vs SVG) — cosmetic, decide in apply
- [ ] Transition rule on/off default — design marks optional; apply may ship gated by reduced-motion