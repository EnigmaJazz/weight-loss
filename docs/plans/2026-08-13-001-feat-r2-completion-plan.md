---
title: "feat: Complete R2 — quest icons, weekly objectives, collectibles, celebrations"
type: feat
status: active
date: 2026-08-13
origin: docs/brainstorms/2026-08-13-r2-completion-requirements.md
---

# Complete R2 — Quest Icons, Weekly Objectives, Collectibles, Celebrations

## Overview

This plan executes the full R2-completion scope from the requirements doc: (1) a nine-domain inline-SVG quest icon set plus a cartoon-fox rework across every fox instance; (2) Mon–Sun weekly objectives (10 quests / 3 good days, +40 XP each, awarded when met, forward-only from a per-user activation stamp with a first-partial-week exemption) surfaced on Today and Journey; (3) a cosmetic collectibles system derived monotonically from history (achievement families, goal checkpoints, meal-day streaks 7/30/100, weekly first-meets) with a Journey shelf and World island accent; (4) a sequential celebration queue (level-up banner, quest delight, achievement toast, weekly-met and collectible-earn toasts) under the reduced-motion gate.

## Problem Frame

R2's exit condition — *opening and completing tasks feels rewarding even without AI* — is unmet in four places: quest cards carry no iconography, there is no weekly rhythm or reward moment, there is nothing to collect beyond achievement rows, and celebrations stop at confetti. The plan completes the release's reward loop. Full motivation, user stories, and success criteria: see the origin document.

## Requirements Trace

- R1–R4: Quest icons & mascot — nine-domain icon set, explicit domain mapping, cartoon fox rework, inline-SVG delivery, decorative aria-hidden, motion gate.
- R5–R9: Weekly objectives — Mon–Sun weeks, 10 quests / 3 good days (momentum Good/Great), +40 XP each when met, forward-only from activation, first-partial-week exemption, Today + Journey surfaces, first-ever weekly collectible.
- R10–R13: Collectibles — cosmetic, four sources, always-rendered shelf with silhouettes, World accent, monotonic never-relock, retroactive unlock from full history.
- R14–R18: Celebrations — level-up banner, quest completion delight, achievement toast, weekly-met + collectible-earn toasts, sequential priority queue, all motion-gated.
- Success criteria: user-visible reward loop (see origin) and planner handoff without invented behavior (see Open Questions — none block planning).

## Scope Boundaries

- Mascot personality/reaction states (later release) — the fox rework is visual only.
- No gameplay effect or economy for collectibles; no new notification types; no AI (RELEASE 5+); no World expansion beyond the accent (RELEASE 7).
- No changes to the quest-generation engine, XP curve constants, or momentum semantics — they are reused as-is.

### Deferred to Separate Tasks

- Backlog reconciliation (`docs/backlog.md` R2 rows) and ROUTER-LOG rows: cycle-close housekeeping, done with the SDD archive phase.

## Context & Research

### Relevant Code and Patterns

- **Persisted-engine pair precedent** (the shape this plan's weekly backend follows): `rewards.py` pure engine + `database.py` `active_rewards` table (composite PK `(user_id, key)`), `reconcile_active_rewards` startup reconcile, `_reconcile_active_rewards(conn, user_id)` upsert diff, before/after diff helpers (`newly_earned_checkpoints`), `_celebrate_if_earned` in routes.
- **XP derivation**: `xp.py` pure curve (`threshold_for_level`, `level_from_xp`, `level_progress`, `title_for_level`) and the single SUM in `Database.total_xp_for_user` (database.py:1350-1360). Docstrings say "no ledger is ever written" — this plan changes that contract for weekly awards only; the `reward_events` DROP trap (database.py:41) forbids that name.
- **Derived engines to mirror**: `momentum.py` (`classify_day`, `is_successful`, `momentum_facts(user_id, start, end)` week-bounded already); `achievements.py` `states()` with earliest-qualifying-date `unlocked_at` (the monotone-earliest-crossing model); `streaks.py` `meal_streak` (the only day-based counter) and `_run_backward` walker (basis for a full-history first-crossing scan).
- **Schema conventions**: `SCHEMA_STATEMENTS` additive `CREATE TABLE IF NOT EXISTS` inside one `_tx` (database.py:40-192, 306-312); `_migrate_*` PRAGMA pattern for additive columns; entry-style dataclasses in `models.py` (no owner id); `_from_row` mappers; `_local_now`/`_today` time helpers; startup wiring in `init_app_state` (main.py:68-84).
- **Routes**: `require_user` + `get_db` deps, `await run_db(...)`, `asdict`-serialized engine states; `/api/achievements` (routes.py:1546-1555) is the template for `/api/weekly` and `/api/collectibles`; `complete_quest` already returns `level_up: {from, to}` via before/after `level_from_xp` diff (routes.py:1358-1376).
- **SPA**: read-diff celebration state (`prevEarned`/`prevAchievementKeys`/`prevWorldStage`, app.js:558-570, updated only on fulfilled reads); `loadQuestsAndXp` sequencing; `mutateQuest` refresh path; `toast()` single-slot (app.js:41-52); `fireConfetti` + `matchMedia` reduced-motion early-return; CSS reduced-motion block (style.css:980-1017); token-only styling incl. `--fox` tokens; `isoWeekStart` in format.js; `QUEST_DOMAIN_ICONS` map will mirror the `EXERCISE_TYPES`/`HABIT_TYPES` drift-guard convention (test_spa_gate.py:78-91).
- **Fox instances** (all reworked in Unit 1): favicon data-URI (index.html:8), header `.mascot` (index.html:33), World island stage-5 `.island-fox` (index.html:453-465), `static/icons/icon-192.png`/`icon-512.png` via `make_icons.py` (+ `--fox` tokens). `tests/test_icons.py` byte-pins the generated PNGs.
- **Tests**: `tests/conftest.py` harness (tmp_path DB, stubbed push, `onboarded_client`, `pair` isolation); `test_spa_gate.py` gate pins + drift guards; `tests/frontend/*.test.mjs` node:test importing real `static/format.js`; `tests/smoke-ui.sh` (728 lines) playwright driver with `step_ok`/`assert_find` helpers.

### Institutional Learnings

- `docs/solutions/workflow-issues/hybrid-routing-missing-tdd-evidence-2026-08-13.md` — strict-TDD apply-progress is a verify gate: the orchestrator merges lane results into `apply-progress.md` with the 7-column TDD Cycle Evidence table + Work Unit Evidence before verify; RED rows must be truthful and cross-checkable; failed→passed ledger settle requires a committed remediation.
- Prior cycles: per-slice diffs ≤400 lines (S4a's 610 needed a maintainer exception; today's UI slices are line-hungry — forecast conservatively); smoke scratch server conventions (`setsid -f env WEIGHT_LOSS_DB/WEIGHT_LOSS_VAPID_KEYS` at /tmp, `pkill -f "uvicorn main:app"`, restart after commits for the `?v=` stamp); `node --test tests/frontend/*.test.mjs` glob (bare dir fails on Node 26); gga STRICT-mode retry; `test_icons.py`/`make_icons.py`/PNGs must regenerate atomically together; palette lockstep test forbids hex literals.
- R2 world-xp-island precedent: UI bundles ran on the frontend lane (frontend-dev → frontend-apply) with orchestrator merging results — this cycle's UI slices use the same lane.

## Key Technical Decisions

- **Weekly XP lives in a persisted award table** (`weekly_awards`), summed alongside quest XP in `total_xp_for_user`. Derivation alone cannot create XP that corresponds to no quest row; the single-source SUM is the one structural change to the XP economy, and the xp.py contract docstring is updated with it. The table name is NOT `reward_events` (dropped on every init).
- **Activation is a per-user stamp** (confirmed): recorded on the first weekly-state read; the first counted week is the first full Monday at/after the stamp; the partial week is exempt; weeks before the stamp award nothing. A small persisted row per user (or additive settings key) carries it.
- **Awards reconcile on the read/mutation path, not the scheduler** (`active_rewards` precedent): met-goal detection computes met-ness from the week's facts; a pure diff against `weekly_awards` rows persists the +40 rows exactly once per (week, goal) and emits the met-flip signal for the toast. Startup reconcile (`init_app_state` hook) backfills any week that flipped met while the app was closed.
- **Collectibles are fully derived, monotonically** (achievements precedent): every source derives an earliest-qualifying date over full history — achievement families from `achievements.states()`, checkpoints from weight-history earliest crossing of each threshold, meal-day streak milestones from the first maximal run reaching 7/30/100 consecutive meal days, weekly tokens from the earliest qualifying week. Earliest-crossing is monotone by construction: no unlock ledger, no relock, retroactive-at-activation for free.
- **The icon map lives in `format.js`** (node-testable, UMD), drift-guarded against `QUEST_POOL` domains by a gate test; nine inline-SVG strings; icons are aria-hidden decorative.
- **Celebration queue is client-side and sequential**: one queue with priority level-up > achievement > weekly/collectible > quest delight; the single-slot `toast()` is extended to queue; each detector follows the existing null-until-first-successful-read diff pattern; everything early-returns under reduced motion.
- **One plan, chained delivery**: the full brainstorm scope ships as one SDD change with multiple stacked work-unit slices (each ≤400 changed lines), reusing the auto-chain stacked-to-main strategy already cached for this project.

## Open Questions

### Resolved During Planning

- Weekly XP storage: persisted `weekly_awards` table summed into `total_xp_for_user` (above).
- Activation semantics: per-user first-load stamp (confirmed in synthesis).
- Collectible monotonicity: earliest-crossing derivation, no unlock ledger (above).
- Good-day count: reuse `momentum.classify_day`/`is_successful` over week-bounded `momentum_facts` (verified supported).
- Streak milestones: `meal_streak` day-based history walk (verified the only day-based counter).

### Deferred to Implementation

- Exact SVG shapes/sizes/stroke treatment for the nine icons and the fox face (visual design during the frontend slice).
- Exact toast/banner copy and element naming.
- Whether the activation stamp rides a new small table or an additive settings key (both fine; schema chosen in Unit 2 against the `_migrate_*` conventions).
- Final weekly-facts gather shape (one bounded query vs reuse of existing gathers) against real code.

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

**Weekly objective data flow (read/mutation path):**

```
quest rows + log rows (per week)
        │  week-bounded gathers (momentum_facts + done-quest count)
        ▼
weekly.py (pure): met_quests(week facts), met_good_days(week facts), targets 10 / 3
        │
        ▼
database.py: diff vs weekly_awards(week, goal) rows → INSERT missing awards (+40 each)
        │                                      │
        ▼                                      ▼
total_xp_for_user = Σ done quests + Σ weekly_awards   met-flip signal → /api/weekly payload
```

**Collectible derivation (earliest crossing over full history, monotone):**

```
achievements.states()      → 6 family tokens   (unlocked_at = family's first-earn date)
weight history × thresholds → 5 checkpoint tokens (unlocked_at = earliest weight ≤ threshold)
meal-day history walk      → 3 streak tokens    (unlocked_at = Nth consecutive day in first run)
week facts (full history)  → 2 weekly tokens    (unlocked_at = earliest qualifying week)
        └─ all derived, no persisted unlock state; shelf = catalog ∪ unlock dates
```

**Celebration queue:**

```
detectors (level diff / quest diff / achievement keyset diff / weekly met flip / collectible keyset diff)
        → enqueue with priority → render one at a time (banner → toasts → card delight)
        → reduced-motion: static outcome only, no animation
```

## Implementation Units

- [ ] **Unit 1: Quest icon catalogue + cartoon fox rework**

**Goal:** Nine-domain inline-SVG icon set in `format.js` with an explicit domain map; the fox face rebuilt as a cartoon fox in every fox instance; generated PWA icons regenerated atomically.

**Requirements:** R1, R2, R3, R4

**Dependencies:** None

**Files:**
- Create: `tests/frontend/icons.test.mjs`
- Modify: `static/format.js`, `static/index.html`, `static/app.js` (icon map consumption), `static/icons/make_icons.py`, `static/icons/icon-192.png`, `static/icons/icon-512.png`, `tests/test_icons.py`, `tests/test_spa_gate.py`, `tests/smoke-ui.sh`

**Approach:** The icon map is a `QUEST_DOMAIN_ICONS` literal (six stored domains from `QUEST_POOL` + strength/sleep/recovery) of inline-SVG strings registered on the `WeightFormat` export, consumed by `renderQuests` and `renderQuestHistory` as aria-hidden decorative icons keyed on the quest's stored `domain` value — no aliasing. The fox face is redrawn once and applied to favicon, header mascot, island stage-5 group, and `make_icons.py` (palette + shapes); PNGs and their byte-pins regenerate in the same change; `--fox` tokens stay (the rework changes shapes, not palette). Gate test pins the map's keys against `QUEST_POOL` domains (drift guard) and the icon SVG strings' presence.

**Execution note:** Test-first per the strict-TDD contract: node contract tests for the map keys and SVG presence before the markup pass; RED = map absent.

**Test scenarios:**
- Happy path: map contains exactly the six stored domains plus strength/sleep/recovery, each with a non-empty SVG string.
- Happy path: quest row with stored domain "movement" renders the movement icon (gate pin + node test on the map).
- Edge case: an unrecognized domain key raises/loudly fails (catalog drift), mirroring the achievements KeyError precedent.
- Edge case: reduced-motion users see the icon statically (no icon animation exists by design; pin "no icon motion rule" in the reduced-motion block).
- Integration: favicon/header/island/make_icons all reference the new face shape; `test_icons.py` byte-pins pass after regeneration; smoke asserts icon presence on quest rows and the mascot visibility pin stays green.

**Verification:** Node suite green incl. new icon tests; `test_icons.py` regenerated and green; gate suite + smoke green with quest-row icons and no placeholder regression.

- [ ] **Unit 2: Weekly objectives backend**

**Goal:** Pure weekly engine, week-bounded facts gather, persisted awards + per-user activation stamp, `GET /api/weekly` with met-state, and XP total including weekly awards.

**Requirements:** R5, R6, R7, R9 (token side deferred to Unit 4)

**Dependencies:** Unit 1 (none logically; may land after it)

**Files:**
- Create: `weekly.py`, `tests/test_weekly.py`
- Modify: `models.py`, `constants.py`, `database.py`, `routes.py`, `xp.py` (docstring contract), `tests/test_xp.py`, `tests/test_api.py`

**Approach:** `weekly.py` is pure: week identity via `date.isocalendar()` (Mon–Sun), target constants (10 quests, 3 good days), met-ness from week facts, activation-week exemption rule. `database.py` adds the `weekly_awards` table (`CREATE TABLE IF NOT EXISTS`, composite PK `(user_id, week_start, goal)`, CHECK on goal), the activation stamp storage, week-bounded gathers (done-quest count per week + good-day count via `momentum_facts` + `is_successful`), and the reconcile that inserts missing award rows exactly once per (week, goal). `total_xp_for_user` sums quest XP + award XP (single change to the XP contract; xp.py docstring updated). `GET /api/weekly` returns current-week progress/met state, past-week history (bounded), and a met-flip signal; it also stamps activation on first read. Startup reconcile backfills awards for weeks that flipped while closed.

**Execution note:** Test-first per strict-TDD: pure-engine tests (week boundaries, exemption, met thresholds) before DB/route work; RED = engine absent.

**Test scenarios:**
- Happy path: a week with 10+ done quests is met for the quests goal; a week with 3+ Good/Great days is met for the days goal; +40 XP each lands in the XP total exactly once.
- Edge case: exactly 10 quests / exactly 3 good days meet; 9 / 2 do not; a Spark-only day never counts.
- Edge case: activation stamp mid-week → partial week exempt, first counted week is the next Monday; weeks before the stamp award nothing even if met.
- Edge case: award idempotency — repeated reads/mutations of a met week never double-pay (diff-reconcile proof).
- Error path: user with no data → empty progress, no awards, activation stamped.
- Integration: completing the 10th quest of the week (via the quests route) flips the met state on the next weekly read and the level chip includes the +40.

**Verification:** `test_weekly.py` + XP tests green (SUM now includes awards); API tests green; pyright clean; startup reconcile covered.

- [ ] **Unit 3: Weekly objectives UI**

**Goal:** Today-screen live progress card (both bars, met states, toast on met flip) and Journey status/history card.

**Requirements:** R8 (R18's weekly toast signal is consumed here; visual part of R18 lands in Unit 6)

**Dependencies:** Unit 2 (API)

**Files:**
- Modify: `static/index.html`, `static/app.js`, `static/style.css`, `tests/test_spa_gate.py`, `tests/smoke-ui.sh`

**Approach:** A `#weekly-card` on Today with two progress rows (quests, good days) driven by `/api/weekly`; met state flips the bar and fires the weekly-met signal (queued toast in Unit 6); Journey gets the weekly status/history rendering. Token-only styling, dark-mode via token redefinition, motion-gated. Follows the frontend lane (frontend-dev design/verify → frontend-apply) with screenshot verification in both themes.

**Execution note:** Test-first per strict-TDD: gate pin RED before markup (container absent), then smoke pins.

**Test scenarios:**
- Happy path: fresh user sees both bars at 0 with correct labels; completing quests advances the bar after refresh.
- Edge case: activation-week exemption — card shows the countdown to the first counted week (or no bars) before activation Monday.
- Edge case: met state renders ("met" style + check) for the remaining days of the week without double-XP text.
- Integration: Journey history shows past weeks' met/unmet status; smoke covers both themes and reduced-motion (static rendering).

**Verification:** Gate suite + smoke green; visual verification both themes; no placeholder copy.

- [ ] **Unit 4: Collectibles backend**

**Goal:** Pure collectibles engine deriving all four source families with earliest-crossing unlock dates; facts gather; `GET /api/collectibles`.

**Requirements:** R10, R11, R13, R9 (weekly tokens)

**Dependencies:** Unit 2 (weekly facts reuse)

**Files:**
- Create: `collectibles.py`, `tests/test_collectibles.py`
- Modify: `models.py`, `database.py` (facts gather: achievement states reuse, weight history vs thresholds, meal-day history walk, weekly facts), `routes.py`, `tests/test_api.py`

**Approach:** `collectibles.py` is pure: catalog = achievement families (from `achievements.states()`), checkpoints (earliest weight-entry date ≤ each threshold from `checkpoint_thresholds`), meal-day streak milestones (first maximal run reaching 7/30/100 consecutive meal days over full history — a `_run_backward`-style walk), weekly tokens (earliest qualifying week over full history, no activation gate for the token). All unlock dates are earliest-crossing → monotone by construction, never relock, retroactive at activation. Facts gather in one ownership-scoped `_tx` snapshot (achievements precedent). `GET /api/collectibles` serializes catalog order with `{key, title, earned, unlocked_at}` shape mirroring `/api/achievements`.

**Execution note:** Test-first per strict-TDD: pure-engine RED (earliest-crossing cases) before gather/route.

**Test scenarios:**
- Happy path: each source unlocks exactly once at its earliest qualifying date (achievement family, checkpoint crossing, 7/30/100 meal-day runs, weekly first-meet).
- Edge case: checkpoint relock scenario — weight dips below threshold, then rises above, then crosses again → token date is the FIRST crossing; never relocks.
- Edge case: streak breaks at 29 days then later reaches 30 → token from the later run; a 30-day run followed by a break stays earned.
- Edge case: pre-activation history qualifies → token earned with its historical date at first load (retroactive).
- Error path: user with no data → all locked, no crash.
- Integration: `/api/collectibles` returns catalog order with earned/locked flags; weekly tokens align with Unit 2's first-ever-met semantics.

**Verification:** `test_collectibles.py` + API tests green; pyright clean; catalog pinned.

- [ ] **Unit 5: Collectibles UI**

**Goal:** Journey shelf card (always rendered: earned art + dates, locked silhouettes) and World island accent showing the most recent earn.

**Requirements:** R12

**Dependencies:** Unit 4 (API), Unit 1 (icon/fox coherence)

**Files:**
- Modify: `static/index.html`, `static/app.js`, `static/style.css`, `tests/test_spa_gate.py`, `tests/smoke-ui.sh`

**Approach:** `#collectibles-card` on Journey after achievements; data-driven rows (earned/locked), silhouette styling for locked, unlock dates on earned, latest-earn accent element on the World island (data-driven, ordering by unlock date, most recent wins). Frontend lane with both-theme screenshot verification. No hex literals; token-only.

**Execution note:** Test-first per strict-TDD: gate pin RED before markup.

**Test scenarios:**
- Happy path: fresh user sees the full shelf all locked (silhouettes, no dates); earned tokens show art + "Unlocked DD/MM/YY".
- Edge case: empty/silent API failure → scoped error like the momentum card (failure-scoped, other cards render).
- Edge case: several tokens unlock in one refresh → accent shows the latest unlock date.
- Integration: unlocking via checkpoint/streak/weekly (Unit 2/4) appears in the shelf on next Journey load; smoke pins card order and both themes.

**Verification:** Gate suite + smoke green; visual verification both themes; placeholder absent.

- [ ] **Unit 6: Celebration queue**

**Goal:** Sequential celebration queue — level-up banner, quest-complete delight, achievement toast, weekly-met and collectible-earn toasts — priority-ordered, once per transition, reduced-motion gated.

**Requirements:** R14, R15, R16, R17, R18

**Dependencies:** Units 2, 4 (signals), 3, 5 (surfaces)

**Files:**
- Create: `tests/frontend/celebrations.test.mjs`
- Modify: `static/format.js` (pure diff/queue helpers: quest-status diff, weekly met diff, collectible keyset diff, priority ordering — node-testable), `static/app.js` (queue, banner element, detector wiring, extended `toast()`), `static/index.html` (banner element), `static/style.css` (banner/queue styling + reduced-motion neutralizations), `tests/test_spa_gate.py`, `tests/smoke-ui.sh`

**Approach:** Detectors map to existing read-diff patterns: server `level_up` payload (already emitted by quest completion) + client level diff on load for the banner; quest-status diff (new `prevQuestStatuses`-style set) for the card delight; `prevAchievementKeys` (exists) for the achievement toast; weekly met-flip and collectible keyset diffs (new, mirroring the same null-until-first-success pattern) for their toasts. All events enqueue into one sequential queue with fixed priority (level-up > achievement > weekly/collectible > quest delight); `toast()` becomes queue-aware; the banner is a non-blocking overlay, auto-dismiss ~3s + tap; reduced-motion early-return before any animation.

**Execution note:** Test-first per strict-TDD: pure queue/diff helpers in `format.js` pinned by node tests (ordering, once-per-transition, suppression matrix) before app.js wiring.

**Test scenarios:**
- Happy path: a refresh carrying a level-up, an achievement unlock, and a weekly met fires banner → achievement toast → weekly toast in order, each exactly once.
- Edge case: reload does not re-fire past transitions (null-until-first-success markers); cleared storage re-celebrates (documented, matches existing behavior).
- Edge case: simultaneous events queue sequentially with no overlap (pin the queue length/order contract).
- Edge case: reduced-motion → static outcomes only, no animation, no confetti.
- Integration: quest completion route's `level_up` payload drives the banner; weekly met flip (Unit 2) and collectible earn (Unit 4) enqueue their toasts; smoke asserts the banner/toast presence after a level-crossing completion and under reduced motion.

**Verification:** Node suite green (queue/diff helpers), gate suite + smoke green, visual verification of the banner in both themes.

## System-Wide Impact

- **Interaction graph:** `total_xp_for_user` change ripples into `/api/xp`, the Today XP chip, level title, and the World island stage (all consumers of the total — level curve unchanged, so all remain consistent). Quest mutation paths (`_ensure_today_quests`, `complete_quest`) and `loadData`/`loadJourneyCards` refreshes are the award/toast trigger points.
- **Error propagation:** weekly and collectibles reads follow the achievements pattern — one `_tx` snapshot per user, `run_db` threading; API failures scoped per card in the SPA (momentum-card precedent).
- **State lifecycle risks:** award double-pay (mitigated by diff-reconcile + composite PK upsert); relocking tokens (eliminated by earliest-crossing derivation); XP total contract change (mitigated by updating xp.py docstring + `test_xp.py` pins in the same unit).
- **API surface parity:** no existing endpoint changes shape; two new read endpoints (`/api/weekly`, `/api/collectibles`) follow the `/api/achievements` contract.
- **Integration coverage:** cross-layer scenarios unit tests alone will not prove — weekly met flip → XP chip + toast; checkpoint/streak earn → shelf + island accent; level crossing → banner (smoke + API tests).
- **Unchanged invariants:** quest generation/rotation, XP curve constants, momentum classification semantics, streak engine semantics, notification types, palette tokens — none change; the plan only adds surfaces around them.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| XP-total contract change breaks existing pins/docs | Change is one SUM extension; `xp.py` docstring + `test_xp.py` updated in the same unit; all XP consumers are derived from the total, so no shape change |
| Line-hungry UI slices blow the 400-line budget (S4a 610 precedent; this scope is ~1800 lines total) | Chained stacked-to-main slices, each unit ≤400; icons/fox slice and celebration slice may need tighter trimming — forecast per-slice during task planning and use the auto-chain path |
| Fox rework breaks pinned artifacts (`test_icons.py` byte-pins, palette lockstep, smoke mascot pins) | Regenerate PNGs + pins atomically in Unit 1; keep the palette (`--fox` tokens) unchanged; smoke pins updated in the same commit |
| Weekly award idempotency under repeated reads/restarts | Composite-PK upsert diff + startup reconcile; idempotency tests in Unit 2 |
| Celebration once-per-transition markers re-fire after storage clears | Accepted, documented (matches existing achievement/stage-up behavior) |
| gga STRICT-mode false-fail on long preambles | Retry pattern established (3× precedent); never a project-level override |

## Documentation / Operational Notes

- `xp.py` docstring contract update ("derived solely from done quests" → quests + weekly awards) ships with Unit 2.
- `docs/backlog.md` R2 rows and ROUTER-LOG rows updated at cycle close (archive phase).
- Scratch-server `?v=` restart convention applies to every UI slice; smoke on scratch port with /tmp DB + VAPID.
- Apply-progress must carry the strict-TDD 7-column evidence table with Safety Net baselines (verify gate per the 2026-08-13 learning doc).

## Sources & References

- **Origin document:** `docs/brainstorms/2026-08-13-r2-completion-requirements.md`
- Related code: `rewards.py`, `achievements.py`, `momentum.py`, `streaks.py`, `xp.py`, `quests.py`, `constants.py` (QUEST_POOL, XP constants), `database.py` (SCHEMA_STATEMENTS, `total_xp_for_user`, `momentum_facts`, `achievement_facts`, reconcile patterns), `routes.py` (`get_achievements`, `complete_quest`), `static/format.js`, `static/app.js`, `static/index.html`, `static/style.css`, `static/icons/make_icons.py`
- Related archives: `openspec/changes/archive/2026-08-10-r1-quests-xp/`, `2026-08-11-r2-achievements/`, `2026-08-13-r2-world-xp-island/`, `2026-08-08-game-appearance/`, `2026-08-08-goals-dashboard/`
- Learning: `docs/solutions/workflow-issues/hybrid-routing-missing-tdd-evidence-2026-08-13.md`
