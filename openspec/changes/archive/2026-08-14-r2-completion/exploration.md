# Exploration: R2 Completion — Quest Icons, Weekly Objectives, Collectibles, Celebrations

Date: 2026-08-14 · Change: `r2-completion` · Artifact store: openspec

## Topic

Verify the plan (`docs/plans/2026-08-13-001-feat-r2-completion-plan.md`) against the real codebase across its six implementation units: icon catalogue + fox rework, weekly backend, weekly UI, collectibles backend, collectibles UI, celebration queue. Every technical assumption was checked against source, tests, specs, and archived changes.

## Current State (verified findings)

### 1. `total_xp_for_user` — single-SUM location and the "done quests only" pins (Unit 2)

- `Database.total_xp_for_user` (database.py:1350-1360) is the one XP source: `SELECT COALESCE(SUM(xp_value), 0) AS total FROM quests WHERE user_id = ? AND status = 'done'`. Docstring explicitly contracts: *"no ledger is ever written (reward_events is dropped on every schema init)"*.
- `xp.py:6-8` mirrors the contract: *"Totals are derived solely from done quests (SUM in database.py); this module never writes or reads a ledger."*
- **Spec-level contract also exists**: `openspec/specs/xp-progression/spec.md:11` — *"Total XP MUST equal the per-user sum of `xp_value` for quests whose status is `done`… XP MUST NOT use a mutable ledger or `reward_events`."* The plan only lists the xp.py docstring + `test_xp.py` for the contract update; **the xp-progression delta spec MUST carry a MODIFIED requirement too**, or archive-merge conflicts with the main spec.
- Tests: `tests/test_xp.py::TestXpPersistence::test_total_xp_sums_only_done` (lines 135-164) pins 60 (20+40), per-user isolation, and 0 for an empty user. Extending the SUM with `+ COALESCE((SELECT SUM(xp_value) FROM weekly_awards WHERE user_id = ?), 0)` keeps all three pins green unchanged (no award rows exist in those fixtures) — only the docstring/comment + spec wording change. All XP consumers (routes `/api/xp`, Today chip, world stage) derive from the total, so the level curve stays stable; no consumer shape changes.

### 2. `momentum_facts(user_id, start, end)` — week-bounded good-day counting (Unit 2)

- Call shape confirmed (database.py:1379-1402): `momentum_facts(user_id: int, start: str, end: str) -> list[MomentumDayFacts]`, inclusive `[start, end]` on ISO date strings, sorted ascending; each fact carries `date`, `assigned_quests`, `done_quests`, `log_rows`. The shared gather `_momentum_day_rows(conn, user_id, start, end)` (database.py:1453-1476) already supports the date bounds (`AND date BETWEEN ? AND ?`), so no new gather is needed for the week window — the plan's "final weekly-facts gather shape" open question is resolved: reuse `momentum_facts` per Monday..Sunday.
- `momentum.classify_day` (momentum.py:34-56): Good Day = ≥2 actions; Great Day = all assigned done + ≥1 action; **first branch `assigned_quests == 0 → none`** — a day with log rows but zero current assignments (all-replaced day) is not successful. `is_successful` (momentum.py:59-61) = Good/Great only. This is the existing momentum semantic R5 points to; the weekly engine must reuse `classify_day`/`is_successful` verbatim. Weekly counts: quests objective = `sum(f.done_quests)` over the week; good-days objective = `sum(is_successful(classify_day(f)))`. A Spark-only day never counts (pins in `tests/test_momentum.py`).

### 3. `meal_streak` / `_run_backward` — earliest-crossing needs a NEW walk variant (Unit 4)

- `streaks.py:92-98` `meal_streak`: builds a `{date: count}` dict (a day with multiple meals = 1 day), then `_run_backward(counts, today, lambda d: d - timedelta(days=1), 1)`.
- `_run_backward` (streaks.py:33-56) walks **backward from today** and stops at the first fully-elapsed break; it computes the *current* streak length. It cannot answer "when did a run first reach N" — **a forward earliest-crossing variant is required** (sort meal days ascending, walk consecutive-day runs, record the first date a run reaches each milestone 7/30/100). The plan's "a `_run_backward`-style walk" is directionally right but must be implemented as a new sibling pure helper (streaks.py or collectibles.py), not reuse.
- Coverage: `tests/test_streaks.py::TestMealStreak` (lines 125-145) covers current-streak semantics (multi-meal one day, empty-today pending, elapsed-empty breaks) — these stay untouched. Collectible milestone tests land in `tests/test_collectibles.py`.

### 4. Checkpoint thresholds — earliest weight-history crossing is derivable (Unit 4)

- `rewards.py:23-34` `checkpoint_thresholds(start, target)`: `(percent, round(start - percent/100 * (start - target), 4))` for 10/25/50/75/100; `[]` when start/target missing or `target >= start`. `compute_baseline` (rewards.py:110-118) = override else oldest entry (min by date); `compute_current` (rewards.py:121-125) = latest (max by date). `active_checkpoints` uses `current <= threshold` — **reaching the threshold counts (<=), not strictly below**.
- Earliest crossing date per threshold: sort weight entries ascending by date, first date with `weight_kg <= threshold_kg`, using the *same* rounded threshold from `checkpoint_thresholds` (reuse, don't recompute — the 4dp banker's rounding is pinned by format.js:218-224 mirror and `tests/test_rewards.py`). Data source: `db.list_entries(user_id)` (database.py:371-378, newest-first — sort ascending in the engine). Baseline-override changes shift thresholds and recompute dates — consistent with how live rewards reconcile.
- The monotone model is fully precedented: `achievements.states()` (achievements.py:130-149) derives `unlocked_at` = earliest qualifying date (min / index-on-sorted / window scans) and `AchievementState(earned, unlocked_at)` is the shape `/api/collectibles` mirrors (routes.py:1546-1555 `/api/achievements` is the template).

### 5. `active_rewards` + reconcile — composite-PK upsert precedent for `weekly_awards` (Unit 2)

- Table (database.py:115-122): composite `PRIMARY KEY (user_id, checkpoint_percent)`, columns `user_id / checkpoint_percent / threshold_kg / earned_at`.
- `_reconcile_active_rewards(conn, user_id)` (database.py:723-758): transactional core on the caller's open conn — derive state, DELETE `existing - derived`, then `INSERT … ON CONFLICT(user_id, checkpoint_percent) DO UPDATE SET threshold_kg = excluded.threshold_kg` (preserves `earned_at`).
- Public `reconcile_active_rewards()` (database.py:706-712) iterates all users; wired in `init_app_state` (main.py:74-75) right after `init_schema()` — the exact hook for the weekly startup backfill. `weekly_awards (user_id, week_start, goal)` with a CHECK on goal follows the identical shape; the `ON CONFLICT` upsert preserves the earn timestamp and makes double-pay structurally impossible.
- Activation stamp: the `settings` table `(user_id, key)` composite PK (database.py:133-139) is the additive-key precedent, **but** `AppSettings`/`DEFAULT_SETTINGS` is the user-editable surface (PUT /api/settings writes arbitrary keys, routes.py:1569-1592) — an activation stamp must NOT ride that surface. A dedicated small row `(user_id, key)` table (settings-table shape, outside the settings API) or a `weekly_state` table is cleaner. `_settings_from_conn` (used by the reconcile) shows the generic key-value read pattern.

### 6. format.js UMD export + drift-guard mechanics (Unit 1, Unit 6)

- format.js is a classic-script UMD (format.js:1-4, 346-349): one `api` object literal → `module.exports = api` (node:test) + `global.WeightFormat = api` (browser); index.html loads it before app.js. New members (icon map, queue/diff helpers) simply join `api`.
- `isoWeekStart` (format.js:90-97) already exists (UTC-deterministic Monday) — the weekly UI reuses it. Existing read-diff helpers to mirror: `newAchievementKeys` (format.js:258-262), `shouldCelebrate` (268-271), `stageChanged` (341-344).
- Drift-guard convention (tests/test_spa_gate.py:78-100): the SPA embeds `EXERCISE_TYPES`/`HABIT_TYPES` array literals (app.js:12, 18) and the gate test regex-extracts + `ast.literal_eval`-compares against `list(constants…)`. For `QUEST_DOMAIN_ICONS` in format.js: `ast.literal_eval` only parses Python literals — either define the map as an array of `["domain", "svg"]` pairs (regex `QUEST_DOMAIN_ICONS\s*=\s*(\[[^\]]*\])` → `ast.literal_eval` works verbatim) or regex-extract the object's keys. The array-of-pairs form makes the drift guard trivial and is the recommended adjustment.

### 7. `level_up` payload — exists on the API, unused by the SPA (Unit 6)

- `complete_quest` (routes.py:1344-1378) returns `{**_quest_dict(updated), "level_up": {"from": L, "to": L'} | None}` computed via before/after `xp.level_from_xp(db.total_xp_for_user)`; idempotent repeats return `level_up: None`. Multi-level jumps land on the landing level (level_after), satisfying R14.
- **Caveat**: `mutateQuest` (app.js:1830-1845) discards the POST response body (`await fetchJson(...)` without reading it) — `"level_up"` appears nowhere in app.js today. The banner detector must (a) capture the response body in `mutateQuest` and (b) add a load-time client-side level diff (mirror the `prevWorldStage` null-until-first-render pattern, app.js:1569-1574) so a reload after a level-crossing completion still banners once. Plan's approach confirmed; the response-capture is a new wiring change.

### 8. Frontend test + smoke conventions (Units 1, 3, 5, 6)

- `tests/frontend/*.test.mjs` (12 files) import the real `static/format.js` via the UMD export and pin mirrors against server vectors (xp.test.mjs ↔ test_xp.py). Run with `node --test tests/frontend/*.test.mjs` (the bare-dir glob fails on Node 26 — documented learning).
- `tests/smoke-ui.sh` (728 lines): playwright-cli driver; helpers `step_ok`/`step_fail`/`assert_find`/`assert_visibility` (lines 45-76); `BASE_URL` arg (default :8000); fresh account per run; header-mascot visibility pin (lines 102-109); tab-clicking for Journey/World assertions. Weekly/shelf/banner pins = new assert blocks; Journey cards need a tab click first.
- Scratch-server conventions (archived): `setsid -f env WEIGHT_LOSS_DB=/tmp/… WEIGHT_LOSS_VAPID_KEYS=/tmp/… .venv/bin/uvicorn main:app --port 8129`, `pkill -f "uvicorn main:app"` cleanup, and `?v=` stamp → scratch server must restart after every static change (r2-world-xp-island exploration).

### 9. `make_icons.py` / `test_icons.py` / palette lockstep — what the fox rework must keep in sync (Unit 1)

- `make_icons.py`: pure-stdlib per-pixel renderer; palette constants `BG #2f7d54 / FOX #eb892c / FOX_DARK #b45c16 / WHITE #fcf8f0 / NOSE #26201e`; geometric fox (triangles/polygons); deterministic; writes icon-192/512.
- `tests/test_icons.py`: (1) render produces full opaque RGBA; (2) committed icons decode to 192/512; (3) **regenerated PNG == committed PNG** (decompressed pixel payload byte-equality). A shape rework in `make_icons.py` must regenerate both PNGs in the same change or test 3 fails.
- `tests/test_palette_lockstep.py`: `#2f7d54` locked across style.css `--accent`, index.html theme-color, manifest theme_color, and make_icons.py `BG`. `--fox`/`--fox-dark` tokens (style.css:37-38, 72) drive island-fox classes (241-242), confetti colors (app.js:1434), gradients (450, 675, 1034) — the plan's "change shapes, not palette" keeps every pin green.
- Three inline-SVG fox instances carry the same geometric shape set and must be redrawn consistently: favicon data-URI (index.html:8), header `.mascot` (index.html:33), World island stage-5 `.island-fox` group (index.html:453-465). No test byte-pins these SVG bodies, but the mascot-visibility smoke pin (smoke-ui.sh:102-109) and world-island gate pins keep the *presence* honest.

### 10. Contradictions / gaps found (Units 2, 5)

- **xp-progression spec pins the opposite of Unit 2** (spec.md:11, "sum of done quests only … no ledger") — delta spec MUST carry a MODIFIED requirement (see §1). Plan lists code/docstring/test updates only.
- **world-island-ui spec forbids exactly what Unit 5 adds** (spec.md:79): *"no … collectible, economy, weekly objective, Coach integration, or new asset MAY be added."* The collectible accent on the World island (and any weekly objective on World) requires a MODIFIED/REMOVED restriction in that domain's delta spec. **This is the plan's biggest uncovered gap** — without it the archive merge conflicts.
- `reward_events` DROP trap confirmed (database.py:41 — `DROP TABLE IF EXISTS reward_events` runs on every schema init); the `weekly_awards` name is safe and free (no table/endpoint/column named weekly exists anywhere; scheduler "weekly" refers only to notification types).
- Institutional learnings (`docs/solutions/workflow-issues/hybrid-routing-missing-tdd-evidence-2026-08-13.md`): strict_tdd:true makes the apply-progress.md TDD Cycle Evidence table a verify gate; UI-lane results must be merged by the orchestrator; RED rows validated by commit-parent inspection; failed→passed settle needs a committed remediation. Plan already carries this.

## Affected Areas

- `database.py` — `total_xp_for_user` SUM extension (1350-1360); `weekly_awards` + activation-stamp tables in `SCHEMA_STATEMENTS` (40-192); reconcile mirroring `_reconcile_active_rewards` (723-758); week-bounded gathers via `momentum_facts` (1379-1402); `list_entries` (371-378) feeds checkpoint crossing.
- `weekly.py` (new) / `collectibles.py` (new) — pure engines mirroring rewards.py/momentum.py/achievements.py.
- `rewards.py` — `checkpoint_thresholds`/`compute_baseline` reused by the collectibles engine (no change).
- `streaks.py` — new forward earliest-crossing walk sibling to `_run_backward`.
- `xp.py` + `tests/test_xp.py` + `openspec/specs/xp-progression/spec.md` — contract wording (quests + weekly awards).
- `openspec/specs/world-island-ui/spec.md` — lift the collectible/weekly-objective prohibition.
- `routes.py` — `/api/weekly`, `/api/collectibles` (achievements template, 1546-1555); `complete_quest` level_up stays (1344-1378).
- `main.py` — startup weekly reconcile hook next to `reconcile_active_rewards` (68-84).
- `static/format.js` — `QUEST_DOMAIN_ICONS` + queue/diff helpers on the UMD `api`; `static/app.js` — icon consumption, weekly/shelf renderers, queue wiring, level_up response capture in `mutateQuest`; `static/index.html` + `static/style.css` — cards, banner, fox instances, motion gate (style.css:980-1017).
- `static/icons/make_icons.py` + PNGs + `tests/test_icons.py` + `tests/test_palette_lockstep.py` — atomic fox rework.
- `tests/test_spa_gate.py` — icon-map drift guard (style of 78-100) + new DOM pins; `tests/frontend/*.test.mjs` — icons/celebrations node tests; `tests/smoke-ui.sh` — weekly/shelf/banner pins.

## Approaches

1. **Weekly XP in a persisted `weekly_awards` table summed into `total_xp_for_user` (plan)**
   - Pros: single XP source keeps level chip/stage consistent; composite-PK upsert makes double-pay impossible; reconcile-on-read + startup backfill precedent; `reward_events` trap avoided.
   - Cons: one structural change to the XP contract (docstring + test + spec delta in the same unit); XP becomes quests + awards (documented).
   - Effort: Low-Medium. **Recommend.**

2. **Weekly XP derived separately and NOT summed into the total (alternative)**
   - Pros: `total_xp_for_user` untouched; no spec-delta in xp-progression.
   - Cons: violates R6 ("XP is recorded in a persisted award source"); the XP chip/level/stage would ignore weekly awards, breaking AE1's "+40 immediately" on the visible total; requires a second XP read everywhere. Rejected.

3. **Collectibles monotonicity: earliest-crossing derivation over full history (plan) vs a persisted unlock ledger**
   - Earliest-crossing: no unlock rows, no reconcile, no migration, retroactive-at-activation free, mirrors `achievements.states()` exactly; meal-day milestones need the new forward walk variant. Ledger: needs its own table + diff machinery + relock guard for no benefit (R13 explicitly prefers derivation; monotone by construction). **Recommend earliest-crossing.**

4. **Activation stamp: dedicated `(user_id, key)` flag table vs a `settings` row**
   - A settings key reuses the composite-PK pattern but leaks onto the user-editable settings surface (PUT /api/settings). A dedicated small table (same shape, outside the settings API) is cleaner. **Recommend the dedicated row** (both are additive; decide in Unit 2 against `_migrate_*` conventions).

5. **Icon map drift guard: array-of-pairs vs object literal in format.js**
   - Array-of-`["domain", "svg"]` pairs lets the gate test reuse the exact `ast.literal_eval` pattern already proven for EXERCISE_TYPES/HABIT_TYPES; object literal needs a bespoke key-extraction regex. **Recommend array-of-pairs.**

## Recommendation

The plan's architecture holds on every verified point. Two adjustments and two gaps to fold in:

- **Adjustment A (Unit 4):** meal-day milestones need a new forward earliest-crossing walk, not a `_run_backward` reuse — implement as a sibling pure helper.
- **Adjustment B (Unit 1):** define `QUEST_DOMAIN_ICONS` as an array of `["domain", "svg"]` pairs so the gate test reuses the proven `ast.literal_eval` drift-guard pattern.
- **Gap C (Unit 2):** ship a MODIFIED requirement in the `xp-progression` delta spec (spec.md:11 pins "done quests only / no ledger" — the exact contract this change extends).
- **Gap D (Unit 5):** amend the `world-island-ui` spec's "no collectible / weekly objective / new asset MAY be added" restriction (spec.md:79) in the same delta, or the archive merge conflicts.

## Risks

- Spec deltas C/D are missing from the plan — archive-merge conflicts and a verify surprise if not added.
- `level_up` payload is emitted but currently discarded by the SPA; the banner needs response capture + a load-time level diff (new wiring, easily missed in the celebration unit).
- Fox rework is atomicity-bound: make_icons.py shapes + regenerated PNGs + test_icons byte-pin + three inline-SVG fox instances + mascot-visibility smoke pin + palette lockstep must land in one unit; any drift fails a pin.
- Weekly award idempotency under repeated reads/restarts — mitigated by composite-PK diff + startup reconcile (mirror the active_rewards proof, test_user_isolation.py).
- UI slices are line-hungry (S4a 610-line precedent; this scope ~1800 lines) — chained stacked-to-main delivery with ≤400-line slices and conservative forecasting is already in the plan.
- `classify_day`'s `assigned_quests == 0 → none` branch means a log-heavy all-replaced day never counts as good — matches R5's "existing momentum definition", but the weekly spec scenarios should pin it to avoid drift.
- XP-total contract change ripples into every XP consumer — all derived from the total, so shape-stable; updated in the same unit.

## Ready for Proposal

Yes — the orchestrator should tell the user: the plan's assumptions verified against the code, with two small adjustments (forward walk variant for streak milestones; array-of-pairs icon map for the drift guard) and two spec-level gaps to carry into the proposal (xp-progression MODIFIED requirement; world-island-ui restriction lift). Proceed to sdd-propose.
