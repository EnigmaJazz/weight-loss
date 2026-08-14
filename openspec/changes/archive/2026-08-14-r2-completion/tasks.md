# Tasks: R2 Completion — Quest Icons, Weekly Objectives, Collectibles, Celebrations

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1950–2100 total: S1 ~400, S2 ~380, S3 ~300, S4 ~400, S5 ~250, S6 ~350 |
| 400-line budget risk | Per-slice Low–Medium; High as one PR |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (S1) → PR 2 (S2) → PR 3 (S3) → PR 4 (S4) → PR 5 (S5) → PR 6 (S6), stacked to main |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| S1 | Nine-domain icons + cartoon fox (atomic w/ make_icons+test_icons) | PR 1 | `node --test tests/frontend/icons.test.mjs` + `pytest tests/test_icons.py tests/test_spa_gate.py` | Scratch server + `bash tests/smoke-ui.sh` (icon presence, mascot, both themes) | Revert `static/*` + `make_icons.py` + PNGs + icon/gate/smoke pins together (atomic) |
| S2 | Weekly backend: pure engine, awards, activation, XP SUM | PR 2 | `pytest tests/test_weekly.py tests/test_xp.py tests/test_api.py tests/test_user_isolation.py` | N/A — httpx ASGITransport client covers auth + isolation in-process | Revert `weekly.py` + `database.py`/`routes.py`/`main.py`/`xp.py` additions; additive tables inert, XP returns to quests-only |
| S3 | Weekly UI: Today progress + Journey history | PR 3 | `pytest tests/test_spa_gate.py` | Scratch server + smoke (bars, exemption, met, both themes) | Revert `static/*` + gate/smoke pins (UI-only) |
| S4 | Collectibles backend: earliest-crossing engine + API | PR 4 | `pytest tests/test_collectibles.py tests/test_api.py` | N/A — in-process API tests (auth + isolation) | Revert `collectibles.py` + `streaks.py` forward walk + gather/route additions (additive API) |
| S5 | Collectibles UI: Journey shelf + World accent | PR 5 | `pytest tests/test_spa_gate.py` | Scratch server + smoke (shelf, silhouettes, accent, both themes) | Revert `static/*` + gate/smoke pins (UI-only) |
| S6 | Celebration queue: banner + toasts + delight | PR 6 | `node --test tests/frontend/celebrations.test.mjs` + `pytest tests/test_spa_gate.py` | Scratch server + smoke (banner after level crossing, reduced motion) | Revert `static/*` + frontend tests (UI-only) |

Chain: each PR rebases on the merged predecessor and targets `main` in order (S1→S2→S3→S4→S5→S6). S1 and S4 are the tightest slices — parametrize tests to stay ≤400. S1, S3, S5, S6 ride the frontend lane (frontend-dev → frontend-apply) at apply time; S2, S4 are backend lanes.

## Slice 1: Quest Icons + Cartoon Fox (PR 1) — frontend lane

- [x] 1.1 RED — Create `tests/frontend/icons.test.mjs`: pin `QUEST_DOMAIN_ICONS` keys = exactly the six stored domains + strength/sleep/recovery, each non-empty SVG string; `iconForDomain("movement")` resolves; unknown domain throws (fail-loud, no aliasing — R1).
- [x] 1.2 RED — `tests/test_spa_gate.py`: drift-guard pin — `QUEST_DOMAIN_ICONS` keys vs QUEST_POOL domains (mirror EXERCISE_TYPES/HABIT_TYPES convention); both quest renderers use `iconForDomain` with `aria-hidden` (R1/R4).
- [x] 1.3 GREEN — `static/format.js`: add `QUEST_DOMAIN_ICONS` array-of-pairs literal (ast.literal_eval-parseable, design decision B) + `iconForDomain(domain)` fail-loud; register on `WeightFormat`.
- [x] 1.4 RED — `tests/test_icons.py`: update byte/pixel pins for cartoon-fox `icon-192.png`/`icon-512.png`; palette lockstep stays token-only (no hex literals; `--fox` tokens unchanged — R2).
- [x] 1.5 GREEN — Cartoon fox rework, atomic: `static/index.html` favicon data-URI + `.mascot`, island stage-5 `.island-fox` group; `static/icons/make_icons.py` new face shape; regenerate PNGs in the same change (R2).
- [x] 1.6 GREEN — `static/app.js`: `renderQuests`/`renderQuestHistory` consume `iconForDomain`, icons `aria-hidden`; reduced-motion block pins "no icon motion" (R3/R4).
- [x] 1.7 GREEN — `tests/smoke-ui.sh`: quest-row icon presence + mascot pin, no placeholder regression (R3/R4).
- [x] 1.8 Verify — node suite + `pytest tests/test_icons.py tests/test_spa_gate.py` + pyright + scratch smoke; commit `feat(icons): nine-domain quest icons and cartoon fox rework`.

## Slice 2: Weekly Objectives Backend (PR 2) — backend lane

- [x] 2.1 RED — Create `tests/test_weekly.py` (pure): `week_start` Mon–Sun + ISO year rollover; exact 10/3 met, 9/2 unmet; Spark/unclassified day excluded (momentum `is_successful` reuse); mid-week activation → partial week exempt, first counted week = next Monday (R5/R7).
- [x] 2.2 GREEN — Create pure `weekly.py` (no I/O): week identity, targets 10/3, met-ness from week facts, exemption rule.
- [x] 2.3 RED — `tests/test_api.py` + `tests/test_user_isolation.py`: GET /api/weekly — 401 unauthenticated; two-user activation independence; first read stamps activation; met flip emitted once; repeated read/reconcile never double-pays (+40 each, ≤80/week) (R6/R7).
- [x] 2.4 RED — `tests/test_xp.py`: SUM includes weekly awards — 20 + 40 done quests + one 40 award = 100 (spec scenario); awards isolated per user.
- [x] 2.5 GREEN — `models.py`: `WeeklyState`/`WeeklyGoalState` dataclasses; `database.py`: `weekly_awards` + `weekly_activation` tables (CREATE IF NOT EXISTS, composite PK (user_id, week_start, goal), CHECK goal IN ('quests','good_days') AND xp_awarded=40 — name is NOT reward_events, dropped on init), `weekly_snapshot` gather (done-quest count + good-day count, week-bounded), `_reconcile_weekly_awards` diff-insert once per (week, goal), activation stamp on first read (R5/R6/R7).
- [x] 2.6 GREEN — `routes.py` GET /api/weekly (require_user + run_db + `met_flips:[goal]`, history capped 12 weeks); `main.py` startup reconcile for activated users; `xp.py` docstring contract → quests + weekly awards (same unit as pin change).
- [x] 2.7 Verify — `pytest tests/test_weekly.py tests/test_xp.py tests/test_api.py tests/test_user_isolation.py` + pyright; commit `feat(weekly): objectives engine, exactly-once awards, activation, XP sum`.

## Slice 3: Weekly Objectives UI (PR 3) — frontend lane

- [x] 3.1 RED — `tests/test_spa_gate.py`: pin `#weekly-card` on Today (container-first: two progress rows) and Journey weekly status/history container (R8).
- [x] 3.2 GREEN — `static/index.html`: `#weekly-card` on Today (quests + good-days rows), Journey weekly card (current/latest status + newest-first history).
- [x] 3.3 GREEN — `static/app.js`: fetch `/api/weekly` (Promise.allSettled, card-scoped failure), render counts/targets, met states, exemption countdown; forward `met_flips` as weekly-met signal for S6 queue (R8).
- [x] 3.4 GREEN — `static/style.css`: token-only bars/status, dark + mobile, reduced-motion static rendering (R17).
- [x] 3.5 GREEN — `tests/smoke-ui.sh`: both themes; exemption state; met state without double-XP text (R8).
- [x] 3.6 Verify — gate + node + pytest + scratch smoke; commit `feat(weekly): Today progress and Journey weekly history`.

## Slice 4: Collectibles Backend (PR 4) — backend lane

- [x] 4.1 RED — Create `tests/test_collectibles.py` (pure): catalogue order pinned (16 tokens: 6 families + 5 checkpoints + 3 streaks + 2 weekly); checkpoint relock — first crossing date wins, never relocks; broken meal runs — 29-day break then 30-day run → later run's day 30, stays earned after another break; pre-activation history qualifies retroactively; weekly token = earliest qualifying week, no duplicate; empty/foreign histories → all locked (R11/R13).
- [x] 4.2 GREEN — Create pure `collectibles.py` (no I/O): achievement-family dates from `achievements.states()`, checkpoint earliest-crossing from weight history, meal-day milestones 7/30/100 from NEW forward walk, weekly tokens from full-history week facts (no activation gate for tokens, R9). Add forward walk to `streaks.py` (`first_run_milestones`) — do NOT touch `_run_backward`/`meal_streak` (R13).
- [x] 4.3 RED — `tests/test_api.py`: GET /api/collectibles — 401; shape `{collectibles:[{key,title,earned,unlocked_at}]}` in catalogue order; two-user isolation (R10).
- [x] 4.4 GREEN — `models.py` `CollectibleState`/`Collectible` dataclasses; `constants.py` `COLLECTIBLE_CATALOG` (ordered 16 keys/titles); `database.py` `collectible_facts(user_id)` one `_tx` snapshot (achievement states reuse, weight history, meal-day entries, week facts); `routes.py` GET /api/collectibles (R10/R11/R12).
- [x] 4.5 Verify — `pytest tests/test_collectibles.py tests/test_api.py` + pyright; commit `feat(collectibles): earliest-crossing engine, catalogue, API`.

## Slice 5: Collectibles UI (PR 5) — frontend lane

- [x] 5.1 RED — `tests/test_spa_gate.py`: pin `#collectibles-card` after achievements on Journey (NOT World — shelf is Journey-only per R12); pin World island latest-earn accent element (R12).
- [x] 5.2 GREEN — `static/index.html`: `#collectibles-card` shelf (data-driven rows), World island accent slot (R12).
- [x] 5.3 GREEN — `static/app.js`: fetch `/api/collectibles` in `loadJourneyCards` (allSettled, scoped failure), render earned (art + "Unlocked DD/MM/YY") / locked silhouettes; latest `unlocked_at` → World accent, none when empty; collectible keyset diff → first-earn signal for S6 toast (R12).
- [x] 5.4 GREEN — `static/style.css`: silhouette + accent token-only styling, dark + mobile, reduced-motion (R12/R17).
- [x] 5.5 GREEN — `tests/smoke-ui.sh`: shelf order, locked silhouettes, accent present only when earned, both themes (R12).
- [x] 5.6 Verify — gate + node + pytest + scratch smoke; commit `feat(collectibles): Journey shelf and World latest-earn accent`.

## Slice 6: Celebration Queue (PR 6) — frontend lane

- [x] 6.1 RED — Create `tests/frontend/celebrations.test.mjs` (pure): priority order level-up > achievement > weekly/collectible > quest delight; once-per-transition (quest-status diff, weekly met diff, collectible keyset diff); unchanged state and failed reads don't advance markers; reduced-motion → static outcomes, no animation (R14–R18).
- [x] 6.2 GREEN — `static/format.js`: pure helpers `questStatusChanged`, `weeklyMetDiff`, `collectibleKeysetDiff`, `enqueueCelebrations` (priority ordering) on `WeightFormat` (R18).
- [x] 6.3 GREEN — `static/app.js`: capture `level_up` from `mutateQuest` response (currently discarded — verified) + load-time level diff (`prevLevel` null-until-first-success); queue-aware `toast()`; banner = non-blocking overlay, ~3s auto-dismiss + tap dismiss; wire achievement keyset diff (existing `prevAchievementKeys`), weekly met + collectible diffs; reduced-motion early-return before any animation/confetti (R14–R17).
- [x] 6.4 GREEN — `static/index.html` banner element; `static/style.css` banner/queue styling + reduced-motion neutralizations (R14/R17).
- [x] 6.5 GREEN — `tests/test_spa_gate.py` + `tests/smoke-ui.sh`: banner + toast presence after level-crossing completion; no replay on reload; reduced-motion static (R14–R18).
- [x] 6.6 Verify — node suite + gate + pytest + scratch smoke (both themes); commit `feat(celebrations): priority celebration queue with banner and toasts`.

## Commit Guidance

Conventional commits, no `Co-Authored-By`. Stacked to main: rebase each PR after the prior merges; PR body shows 📍 dependency diagram (S6 depends on S3/S5 signals, S4 on S2 weekly facts). Tests ride with their unit; every new code path carries its regression test (AGENTS.md rule 5). Each slice diff ≤400 — trim by parametrizing tests, never by dropping pins.
