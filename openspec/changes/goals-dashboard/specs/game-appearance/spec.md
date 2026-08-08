# Delta for game-appearance

> Extends game-appearance (2026-08-08). Re-skins the Today tab into a goals
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