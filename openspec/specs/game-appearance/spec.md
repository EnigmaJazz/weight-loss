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


## Extended by dark-mode (2026-08-08)

### ADDED Requirement: Dark Chart Color Refresh

`static/app.js` MUST keep the `CHART_COLORS` identifier and add a `refreshChartColors()` that re-reads the semantic tokens via `getComputedStyle` into the same mutable object. Chart colors MUST be token-sourced — `app.js` MUST NOT contain hex literals for chart colors. On a theme change, the theme hook MUST call `refreshChartColors()` and redraw any visible chart. `CHART_FONT` MUST remain unchanged.

### MODIFIED Requirement: Design Tokens and Palette Lockstep

A `[data-theme="dark"]` block after `:root` MUST redefine the semantic tokens (--bg #0f172a, --card #1e293b, --text #e2e8f0, --muted #94a3b8, --border #334155) and lighten --accent-dark (≈#58a97e) and --danger, plus adjust --fox, --gold, and --gold-deep for dark surfaces. --accent MUST stay #2f7d54 in both themes. The dark block MUST NOT use a bare `:root {` selector and MUST NOT introduce a media-variant theme-color meta. Toast colors MUST be tokenized as --toast-bg / --toast-text.

## Extended by goals-dashboard (2026-08-08)
 game-appearance (2026-08-08). Re-skins the Today tab into a goals
> dashboard: hero goal-progress ring, upgraded streak tiles, full 5-card
> milestone track. Frontend-only; pinned ids/strings/selectors preserved.

## ADDED Requirements

### Requirement: Goal Progress Ring

The Today tab MUST render a hero goal-progress ring as inline SVG (~120–160px) using `stroke-dasharray` / `stroke-dashoffset`. Progress pct MUST equal `(baseline − current) / (baseline − target)`, clamped to `0..1`; overshoot MUST clamp at `100%` and never exceed the ring. The ring MUST be null-safe and, when `baseline` or `current` or `target` is missing OR `baseline ≤ target` (no loss goal), MUST render an empty state with helper copy (no partial arc). CSS MUST be tokens-only — the track stroke MUST use `var(--border)` and the progress stroke MUST use a token/fox gradient — and MUST NOT hardcode chart palette hex. The `stroke-dashoffset` transition MUST be neutralized by the existing `@media (prefers-reduced-motion: reduce)` block. A center overlay MUST show the rounded pct and the remaining-to-target copy derived from `summary.remaining_*`.

#### Scenario: Happy-path partial progress

- GIVEN baseline 100, current 90, target 80 (goalProgress 0.5)
- WHEN the Today tab renders
- THEN the arc MUST fill 50% of the ring and the center overlay MUST show `50%` plus remaining-to-target copy

#### Scenario: Overshoot clamps at 100%

- GIVEN baseline 100, current 78, target 80 (raw pct 1.1)
- WHEN the ring renders
- THEN the arc MUST NOT exceed `100%` and the overlay MUST show `100%`

#### Scenario: Edge — no loss goal

- GIVEN baseline ≤ target OR any of baseline/current/target is null
- WHEN the ring renders
- THEN it MUST show the empty state with helper copy and MUST NOT draw a partial arc

#### Scenario: Reduced motion neutralizes the arc transition

- GIVEN `static/style.css` and a `prefers-reduced-motion: reduce` UA
- WHEN the ring's stroke-dashoffset transition is inspected
- THEN it MUST be neutralized (no animated sweep) and no `@starting-style` MUST appear

### Requirement: Goal Progress and Threshold Mirror Helpers

`static/format.js` (UMD, loaded before `app.js`) MUST add pure helpers `goalProgress(baseline, current, target)` and `checkpointThresholds(baseline, target)`. `goalProgress` MUST return a `0..1` clamped number, or `null` when any input is missing OR `baseline ≤ target`. `checkpointThresholds` MUST mirror `rewards.checkpoint_thresholds` exactly: `threshold(p) = baseline − (p/100)·(baseline − target)` rounded to 4 decimals for `p` in `(10, 25, 50, 75, 100)`, returning `[]` when inputs are missing or `target ≥ baseline`. Both MUST be covered by `node:test` (`tests/frontend/*.test.mjs`) including boundaries (0%, 100%, overshoot, nulls, `baseline ≤ target`) and a drift guard pinning `checkpointThresholds(100, 80)` to `[98, 95, 90, 85, 80]`.

#### Scenario: Pure helper returns 0..1 or null

- GIVEN `format.js` exported via `WeightFormat` / `module.exports`
- WHEN `goalProgress(100, 90, 80)` and `goalProgress(100, 80, 80)` and `goalProgress(null, 90, 80)` are called
- THEN results MUST be `0.5`, `null` (baseline ≤ target), and `null` respectively

#### Scenario: Drift guard vs rewards.py

- GIVEN `checkpointThresholds(100, 80)` from the JS mirror and `checkpoint_thresholds(100, 80)` from `rewards.py`
- WHEN the node:test drift guard runs
- THEN JS MUST equal `[98, 95, 90, 85, 80]` and MUST match the Python output for the same inputs

### Requirement: Five-Card Milestone Track

The Checkpoints card MUST render five milestone cards for percents `10/25/50/75/100`. Each card state MUST be derived from the `/api/rewards` payload: `earned` when its percent is in the `active_checkpoints` percent set; `pending` otherwise; `next` when its percent equals `next_checkpoint.percent` (or the first pending when `next_checkpoint` is null); and `recently-earned` when its `earned_at` (UTC, max by date, date-granular `YYYY-MM-DD`) is the newest earned. The `100%` card MUST use gold as a fill only — gold MUST NOT appear as text color. Each card MUST show a per-card emoji icon, and card states MUST be expressed via classes + tokens (no inline palette hex). The pinned h2 string `Checkpoints` and id `rewards-card` MUST NOT change.

#### Scenario: Earned, pending, next states

- GIVEN rewards with active `{10,25}` and `next_checkpoint.percent == 50`
- WHEN the track renders
- THEN the 10/25 cards MUST be earned, the 50 card MUST be next, and 75/100 MUST be pending

#### Scenario: 100% gold is fill-only

- GIVEN the 100% card earned
- WHEN its styles are inspected
- THEN gold MUST style the fill/background and gold MUST NOT be applied to any text color property

#### Scenario: Recently-earned highlight is date-granular

- GIVEN two earned cards with `earned_at` `2026-08-07` and `2026-08-08`
- WHEN the track renders
- THEN only the `2026-08-08` card MUST carry the recently-earned class

### Requirement: Goals Dashboard Non-Regression Gates

The change MUST be additions-only: the existing pinned Today-tab ids (`summary-card`, `streaks-card`, `rewards-card`, `summary-stats`, `streak-stats`, `rewards-content`), the h2 strings (`Summary`, `Streaks`, `Checkpoints`), the `Log weight` form, and every `smoke-ui.sh` / `test_spa_gate.py` selector or visible-text pin MUST stay unchanged. `app.js` pinned strings MUST be preserved. No new tab and no backend/API change MUST be introduced. The `format.js` helpers MUST be added to the export `api` object and registered in `main.py` `_JS_SCRIPTS`/`_CSS_HREFS` with `?v=` only when new assets are added.

#### Scenario: Pinned contracts unchanged

- GIVEN the full change applied
- WHEN `smoke-ui.sh`, `test_spa_gate.py`, pytest, and `node:test` run
- THEN every previously-green gate MUST still pass and the pinned ids/strings/selectors MUST remain present unchanged

#### Scenario: No backend or new tab

- GIVEN the diff
- WHEN routes, database, rewards logic, and the tab set are inspected
- THEN no backend file and no new tab MUST have been added or modified

## MODIFIED Requirements

### Requirement: Motivation Surfaces and Mascot

The system MUST apply game styling to the header (fox mascot + playful lockup), summary scoreboard, streak tiles (flame treatment), reward chips (pop-in) + progress track, primary buttons, and auth/onboarding cards incl. the wizard step indicator. Primary buttons MUST apply press physics (`transform: scale(~0.97)` on `:active`). The streak flame pulse MUST render only while the streak is active via a data attribute. The Today tab MUST additionally be re-skinned in place as a goals dashboard — the Summary card housing the hero goal-progress ring, the Streaks tiles upgraded in place (larger flame + count, preserving `.flame` and `dataset.streakActive`), and the Checkpoints card housing the five-card milestone track — with no new tab, no backend change, and no mascot reactions. Visible copy, DOM ids, and `[hidden]` contracts MUST NOT change.

(Previously: Today tab surfaced Summary/Streaks/Checkpoints as disconnected widgets; streak tiles used a small flame. Now the three are unified into one goals-dashboard layout with a hero ring and full 5-card track, streak tiles upgraded in place.)

#### Scenario: Mascot, flame, copy

- GIVEN the served SPA after the change
- WHEN smoke selectors run on the header and streak tile and visible-text pins run
- THEN a fox mascot element and a flame element MUST be present (flame pulse gated by the active-streak data attribute) and every pinned string MUST still appear unchanged

#### Scenario: Today tab becomes goals dashboard

- GIVEN the served Today tab
- WHEN its cards are inspected
- THEN the Summary card MUST contain the hero ring, the Streaks tiles MUST keep `.flame` and `dataset.streakActive` with a larger flame + count, and the Checkpoints card MUST contain the five-card track, with no new tab introduced