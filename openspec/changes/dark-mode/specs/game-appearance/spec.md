# Delta for game-appearance

## ADDED Requirements

### Requirement: Dark Chart Color Refresh

`static/app.js` MUST keep the `CHART_COLORS` identifier and add a `refreshChartColors()` that re-reads the semantic tokens via `getComputedStyle` into the same mutable object. Chart colors MUST be token-sourced — `app.js` MUST NOT contain hex literals for dark chart colors. On a theme change, the theme hook MUST call `refreshChartColors()` and redraw any visible chart. `CHART_FONT` MUST remain unchanged.

#### Scenario: Refresh mutates CHART_COLORS from tokens

- GIVEN `CHART_COLORS` populated from tokens at module scope
- WHEN `refreshChartColors()` runs after `data-theme` flips to `dark`
- THEN `CHART_COLORS` line/grid/muted/tooltip fields MUST reflect the dark token values and the redrawn chart MUST use them, with no hex literal for chart colors in `app.js`

#### Scenario: Redraw only when visible

- GIVEN the Progress panel is hidden when the theme changes
- WHEN the user later switches to the progress tab
- THEN the chart MUST render with the current theme's colors

## MODIFIED Requirements

### Requirement: Design Tokens and Palette Lockstep

`static/style.css` `:root` MUST add tokens for a radius scale, elevation/shadows, spacing, and accent ramps (fox orange `#eb892c`, celebration gold), keeping `--accent: #2f7d54` as the brand anchor. New CSS MUST reference tokens and MUST NOT hardcode palette hex. `#2f7d54` MUST be identical across `style.css` `--accent`, `index.html` `theme-color`, `manifest.webmanifest` `theme_color`, and `make_icons.py` `BG`; a drift-guard test MUST verify the four match. A `[data-theme="dark"]` block after `:root` MUST redefine the semantic tokens — `--bg #0f172a`, `--card #1e293b`, `--text #e2e8f0`, `--muted #94a3b8`, `--border #334155` — and lighten `--accent-dark` (≈`#58a97e`) and `--danger`, plus adjust `--fox`, `--gold`, and `--gold-deep` for dark surfaces. `--accent` MUST stay `#2f7d54` in both themes. The dark block MUST NOT use a bare `:root {` selector and MUST NOT introduce a media-variant `<meta name="theme-color">`. Toast colors MUST be tokenized as `--toast-bg` / `--toast-text` and `app.js` MUST NOT contain dark chart hex literals.
(Previously: `:root` tokens only; no dark block; toast hardcoded `rgba(15,23,42,.92)`.)

#### Scenario: Four locations lockstep

- GIVEN the change applied
- WHEN a drift-guard test parses the four palette locations
- THEN each accent MUST equal `#2f7d54` and new CSS MUST hold no hardcoded palette hex

#### Scenario: Token set present

- GIVEN `static/style.css` is served
- WHEN parsed as an AST
- THEN `:root` MUST declare radius, elevation, spacing, and accent-ramp tokens used by the new components

#### Scenario: Dark token block

- GIVEN `static/style.css` parsed as an AST
- WHEN the dark block selector and declarations are inspected
- THEN a `[data-theme="dark"]` block (not a bare `:root {`) MUST declare `--bg #0f172a`, `--card #1e293b`, `--text #e2e8f0`, `--muted #94a3b8`, `--border #334155`, lightened `--accent-dark` ≈`#58a97e` and `--danger`, and adjusted `--fox`/`--gold`/`--gold-deep`; `--accent` MUST remain `#2f7d54`

#### Scenario: Accent constant across themes

- GIVEN the light `:root` and the dark `[data-theme="dark"]` blocks
- WHEN `--accent` is read from each
- THEN both MUST equal `#2f7d54`, and no `<meta name="theme-color" media="...">` variant MUST exist

#### Scenario: Toast tokenized

- GIVEN `static/style.css` parsed
- WHEN the `.toast` rule is inspected
- THEN it MUST consume `--toast-bg` / `--toast-text` and MUST NOT use a hardcoded `rgba(15,23,42,...)` background

### Requirement: Data Surfaces, Accessibility, and Mobile-Primary

History rows, forms/inputs, tabs, and charts MUST stay clean but token-consistent. Interactive and input elements MUST have ≥48px touch targets and a `:focus-visible` ring. New palette colors MUST meet WCAG AA contrast. The layout MUST default to a single-column stacking baseline with responsive stats/streak grids that collapse on narrow viewports; primary actions MUST sit in thumb-reach positions. Dark text/background pairs MUST meet WCAG AA: `--text`/`--card`, `--muted`/`--card`, and `--accent-dark`/`--card` MUST each be ≥4.5:1.
(Previously: AA only for the light palette.)

#### Scenario: Targets, focus, column

- GIVEN `static/style.css` parsed and the SPA at a narrow viewport
- WHEN input/primary-button rules and the layout are inspected
- THEN min-height MUST be ≥48px, a `:focus-visible` rule MUST be present, and stat/streak grids MUST collapse to one stacked column

#### Scenario: AA contrast

- GIVEN the new text/background token pairs
- WHEN their contrast is computed
- THEN each pair MUST meet the WCAG AA threshold

#### Scenario: Dark AA contrast

- GIVEN the dark token pairs `--text #e2e8f0`/`--card #1e293b`, `--muted #94a3b8`/`--card #1e293b`, `--accent-dark #58a97e`/`--card #1e293b`
- WHEN their contrast ratios are computed
- THEN each MUST be ≥ 4.5:1 (≈13:1, ≈5.0:1, ≈5.0:1)

### Requirement: Test Gates and Non-Regression

`test_spa_gate.py` MUST add assertions for token presence, the fox favicon, the reduced-motion rule, and new asset stamps. `smoke-ui.sh` MUST stay unchanged except for visual selectors on new elements; visible text MUST stay unchanged. All existing pytest, `node:test`, and `smoke-ui.sh` gates MUST keep passing. The dark block MUST NOT use a bare `:root {` selector and MUST NOT add a media-variant `<meta name="theme-color">`; `test_palette_lockstep.py` MUST stay green. `app.js` MUST NOT contain dark chart hex literals; `CHART_COLORS` and `CHART_FONT` identifiers MUST survive. `smoke-ui.sh` MUST add a theme-toggle step asserting `document.documentElement.dataset.theme === "dark"`.
(Previously: gate assertions for light tokens, favicon, reduced-motion, asset stamps.)

#### Scenario: Gates green

- GIVEN the full change applied
- WHEN pytest, `node:test`, and `smoke-ui.sh` run
- THEN previously-green tests MUST still pass and the new gate assertions MUST pass

#### Scenario: Palette lockstep stays green

- GIVEN `test_palette_lockstep.py` parses `--accent` and the HTML theme-color meta
- WHEN the dark block and meta are in place
- THEN the first `--accent` MUST remain `#2f7d54`, no media-variant meta MUST appear, and the lockstep test MUST pass

#### Scenario: Dark-block gate non-regression

- GIVEN `test_spa_gate.py` `_root_block` regex `:root\s*\{([^}]*)\}`
- WHEN the style sheet is parsed
- THEN the dark selector MUST NOT be a bare `:root {` and tokens MUST stay in `:root`