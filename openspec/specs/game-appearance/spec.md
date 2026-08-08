# Delta for game-appearance

## ADDED Requirements

### Requirement: Design Tokens and Palette Lockstep

`static/style.css` `:root` MUST add tokens for a radius scale, elevation/shadows, spacing, and accent ramps (fox orange `#eb892c`, celebration gold), keeping `--accent: #2f7d54` as the brand anchor. New CSS MUST reference tokens and MUST NOT hardcode palette hex. `#2f7d54` MUST be identical across `style.css` `--accent`, `index.html` `theme-color`, `manifest.webmanifest` `theme_color`, and `make_icons.py` `BG`; a drift-guard test MUST verify the four match.

#### Scenario: Four locations lockstep

- GIVEN the change applied
- WHEN a drift-guard test parses the four palette locations
- THEN each accent MUST equal `#2f7d54` and new CSS MUST hold no hardcoded palette hex

#### Scenario: Token set present

- GIVEN `static/style.css` is served
- WHEN parsed as an AST
- THEN `:root` MUST declare radius, elevation, spacing, and accent-ramp tokens used by the new components

### Requirement: Self-Hosted Rounded Typography

The system MUST self-host OFL **Baloo 2** (display + body weights) under `static/fonts/` as woff2 via filename-versioned `@font-face` with a `system-ui` fallback stack, exposed as tokens `--font-display` / `--font-body`. Canvas chart text MUST keep a readable system fallback while the font loads.

#### Scenario: Versioned font face

- GIVEN `static/style.css` parsed as an AST
- WHEN `@font-face` and font tokens are inspected
- THEN a woff2 under `/static/fonts/` MUST carry a cache-busting version segment, `system-ui` MUST be in the fallback stack, and headings/body MUST consume `--font-display` / `--font-body`

### Requirement: Motivation Surfaces and Mascot

The system MUST apply game styling to the header (fox mascot + playful lockup), summary scoreboard, streak tiles (flame treatment), reward chips (pop-in) + progress track, primary buttons, and auth/onboarding cards incl. the wizard step indicator. Primary buttons MUST apply press physics (`transform: scale(~0.97)` on `:active`). The streak flame pulse MUST render only while the streak is active via a data attribute. Visible copy, DOM ids, and `[hidden]` contracts MUST NOT change.

#### Scenario: Mascot, flame, copy

- GIVEN the served SPA after the change
- WHEN smoke selectors run on the header and streak tile and visible-text pins run
- THEN a fox mascot element and a flame element MUST be present (flame pulse gated by the active-streak data attribute) and every pinned string MUST still appear unchanged

### Requirement: Data Surfaces, Accessibility, and Mobile-Primary

History rows, forms/inputs, tabs, and charts MUST stay clean but token-consistent. Interactive and input elements MUST have ≥48px touch targets and a `:focus-visible` ring. New palette colors MUST meet WCAG AA contrast. The layout MUST default to a single-column stacking baseline with responsive stats/streak grids that collapse on narrow viewports; primary actions MUST sit in thumb-reach positions.

#### Scenario: Targets, focus, column

- GIVEN `static/style.css` parsed and the SPA at a narrow viewport
- WHEN input/primary-button rules and the layout are inspected
- THEN min-height MUST be ≥48px, a `:focus-visible` rule MUST be present, and stat/streak grids MUST collapse to one stacked column

#### Scenario: AA contrast

- GIVEN the new text/background token pairs
- WHEN their contrast is computed
- THEN each pair MUST meet the WCAG AA threshold

### Requirement: Motion System and Reduced-Motion Gate

Confetti MUST fire only on a newly-earned checkpoint (JS diff of earned count), MUST be suppressed on first render, and MUST be gated by `prefers-reduced-motion`. Flame pulse, card hover elevation, and chip pop-in MUST likewise be gated by `@media (prefers-reduced-motion: reduce)`. Toast/tab reveals MUST use JS class-swaps, MUST NOT use `@starting-style`, and MUST preserve `[hidden]`. A confetti-eligibility helper MUST be covered by `node:test`.

#### Scenario: Confetti eligibility

- GIVEN a pure confetti-eligibility helper and a prior earned count
- WHEN the earned count increases
- THEN the helper MUST return fire; on first render (no prior count) it MUST return suppress

#### Scenario: Reduced motion

- GIVEN `static/style.css` and `static/app.js`
- WHEN parsed for a `prefers-reduced-motion: reduce` block
- THEN it MUST neutralize confetti, pulse, hover elevation, and pop-in, and no `@starting-style` MUST appear

### Requirement: Fox Favicon and Manifest Theme

The inline SVG favicon in `index.html` MUST be replaced with a fox glyph matching the icon art; the diamond path MUST be removed. `manifest.webmanifest` `theme_color` MUST remain `#2f7d54`.

#### Scenario: Fox favicon

- GIVEN the served `index.html` and `manifest.webmanifest`
- WHEN the favicon data URI and `theme_color` are inspected
- THEN the favicon MUST contain fox art and MUST NOT contain the diamond path `M32 8l14 22`, and `theme_color` MUST equal `#2f7d54`

### Requirement: Asset Pipeline and Icon Regeneration

Every new CSS, JS, and font asset MUST be registered in `main.py` `_CSS_HREFS` / `_JS_SCRIPTS` and served with the `?v=` cache stamp. `make_icons.py`, the committed icon PNGs, and the `test_icons.py` byte-pin MUST be regenerated together in the same change.

#### Scenario: Assets stamped

- GIVEN the served index
- WHEN new CSS/JS references are inspected
- THEN each MUST appear in its main.py tuple and MUST carry `?v=`

#### Scenario: Icons atomic

- GIVEN `make_icons.py`, the icon PNGs, and `test_icons.py`
- WHEN the icon byte-pin test runs
- THEN the committed PNG bytes MUST match the regenerated render output

### Requirement: Test Gates and Non-Regression

`test_spa_gate.py` MUST add assertions for token presence, the fox favicon, the reduced-motion rule, and new asset stamps. `smoke-ui.sh` MUST stay unchanged except for visual selectors on new elements; visible text MUST stay unchanged. All existing pytest, `node:test`, and `smoke-ui.sh` gates MUST keep passing.

#### Scenario: Gates green

- GIVEN the full change applied
- WHEN pytest, `node:test`, and `smoke-ui.sh` run
- THEN previously-green tests MUST still pass and the new gate assertions MUST pass
