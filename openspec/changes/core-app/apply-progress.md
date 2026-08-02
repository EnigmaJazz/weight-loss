# Apply Progress: core-app — Slice 1 (Foundation)

**Change**: core-app
**Slice**: 1 of 3 (stacked-to-main) — branch `slice-1-foundation`, PR #1 → `main`
**Mode**: Strict TDD (active, resolved from openspec/config.yaml `strict_tdd: true`)
**Status**: 4/4 slice tasks complete (1.1, 1.2, 1.3, 1.4) + baseline commit 5.1
**Test counts**: 37 passing at start → 65 passing at end (all green)

## Completed Tasks

- [x] 1.1 Units conversions/BMI — `units.py` (kg→lb, kg→stone, BMI, display view) + `tests/test_units.py`
- [x] 1.2 Rewards redesign — checkpoint thresholds 10/25/50/75/100, active state from latest-dated weight, next checkpoint, band progress; step-based logic replaced in `rewards.py` + `tests/test_rewards.py`
- [x] 1.3 Migration/settings — `active_rewards(checkpoint_percent PK, threshold_kg, earned_at)` replaces `reward_events`; local timestamps for `created_at`/`earned_at`/`sent_at`; `RewardMilestone` removed; `height_cm` added; `milestone_step_kg` retired and rejected
- [x] 1.4 Reward reconciliation — transactional reconcile inside upsert/delete/settings-update; startup reconcile in `main.py`
- [x] 5.1 Baseline commit `chore: establish weight tracker baseline`

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | tests/test_units.py (9 tests) | Unit | existing 37-test suite | ImportError: no `WeightDisplay`/`units` (0/9 pass) | 46 passed (9 new) | kg/lb factor, stone decomposition, BMI exact, missing height, display shape | `KG_TO_LB` constant; WeightDisplay dataclass in models.py |
| 1.2 | tests/test_rewards.py (rewritten, 21 tests) | Unit | suite (46) | ImportError: no `CHECKPOINTS`/`checkpoint_thresholds`/`reward_state` | 55 passed | five thresholds, inclusive equality, regression/revocation, override vs earliest start, band progress edges (0.0/0.5/1.0) | old step functions retained (dead, 4.2 removes); `reward_state` centralizes derivation |
| 1.3+1.4 | tests/test_api.py, tests/test_weight.py (28 new/rewritten) | Integration | suite (55) | 15 failures: missing `active_rewards` table, missing `height_cm`/retired-key contract, old rewards shape | 65 passed (one test bug fixed: re-earn weight 94 → 90 so 50% threshold is actually reached) | local timestamps via `_local_now` monkeypatch; re-earn refreshes `earned_at`; historical upsert moves start; delete revokes; settings update re-derives | 1.3+1.4 landed as ONE commit — the storage migration cannot be green without the reconciliation keeping `active_rewards` consistent (app would break between the two); separate tasks, one atomic deliverable |

## Work Unit Evidence

| Evidence | Required value |
|----------|----------------|
| Focused test command and exact result | `.venv/bin/python -m pytest tests/test_units.py tests/test_rewards.py` → 30 passed; full suite `.venv/bin/python -m pytest -q` → **65 passed in 0.30s** |
| Runtime harness command/scenario and exact result | httpx ASGITransport integration: `tests/test_api.py` exercises upsert→earn, regression→revoke, re-earn→fresh `earned_at`, historical upsert→start change, delete→reconcile, settings update→reconcile, retired-key 422, local timestamps (65/65 green) |
| Rollback boundary | Revert branch `slice-1-foundation` to `main`; slice-1 files: `units.py`, `rewards.py`, `models.py`, `constants.py`, `database.py`, `main.py`, `routes.py` (minimal compat), `tests/test_units.py`, `tests/test_rewards.py`, `tests/test_api.py`, `tests/test_weight.py` |

## Deviations from Design

1. **routes.py minimally touched in slice 1** (design places full API work in 2.1): `SettingsIn` drops `milestone_step_kg` + `extra="forbid"` (spec-required retired-key rejection is a 1.3 test); `upsert_weight` drops the old reconcile call (DB now self-reconciles); `get_rewards` serializes the new checkpoint contract (old milestone data source was deleted — endpoint would 500 otherwise). Full kg/lb/st/BMI summaries, validation, and mutation-reconciliation endpoints remain for 2.1.
2. **1.3+1.4 landed as one commit** (`feat(rewards): migrate to active_rewards with transactional reconciliation`) — the migration cannot land green without reconciliation (see TDD table). Tasks remain separate for verification.
3. **`target >= start` yields no checkpoints** — thresholds are only meaningful when a loss is possible; `checkpoint_thresholds` returns `[]` (design-silent edge, regression-tested).
4. **Dead step code retained**: `milestone_levels`/`next_milestone`/`progress_to_next`/`lost_delta` in rewards.py and `_float` removal only where 1.3's rewrite orphaned it — 4.2 owns the rest (out of slice scope).
5. **Task 5.1 committed inside PR #1** — `main` had zero commits; the baseline must live somewhere, and slice 1 is the first PR.

## Issues Found

- None blocking. `.gga` pre-commit hook is not installed in `.git/hooks` (no `core.hooksPath`); commits proceeded without hook review. Flagged for the orchestrator — the hook either needs wiring or slice 2+ should install it.
- Pyright LSP diagnostics (18) are environment noise: the LSP cannot resolve the project `.venv` (fastapi/pydantic/httpx/pytest unresolved); runtime imports prove fine (65 passed). 4.1 addresses pyright config.

## Status

Slice 1 complete: 4/4 tasks. Ready for verify (orchestrator) → next_recommended: sdd-verify, then slice 2.

---

# Apply Progress: core-app — Slice 2 (Backend)

**Change**: core-app
**Slice**: 2 of 3 (stacked-to-main) — branch `slice-2-backend`, PR #2 → `main`
**Mode**: Strict TDD (active)
**Status**: 2/2 slice tasks complete (2.1, 2.2). PR #1 (slice 1) merged; PR #2 left open for review.
**Test counts**: 65 passing at start → 74 passing at end (all green; 9 new, 2 contract updates)

## Completed Tasks

- [x] 2.1 API display data — `routes.py`: `WeightIn` strict (`extra="forbid"`); `_weight_view` None-safe raw lb/stone/stone_lb/bmi per weight; entries carry `lb`/`stone`/`stone_lb`/`bmi`; summary carries `*_lb`/`*_stone`/`*_stone_lb` for all five values + `*_bmi` on real weights (baseline/current/target, not deltas); rewards active/next checkpoints carry `threshold_lb`/`threshold_stone`/`threshold_stone_lb`. Mutations already self-reconcile via the DB layer (slice 1) — verified through the API. Tests: `tests/test_api.py` (+6 new, 2 contract updates).
- [x] 2.2 Scheduler local time — `scheduler.py` passes the injected tick's own local wall time (`now.strftime("%Y-%m-%d %H:%M:%S")`) to `mark_notification_sent`; `database.py` accepts optional `sent_at` (defaults to fresh `_local_now()` for direct callers). Local HH:MM comparison + local-calendar-date day key were already correct by construction; DST repeated-hour single-send, DST skipped-time fires-on-next-tick, and tick-sourced `sent_at` pinned with regression tests. Tests: `tests/test_scheduler.py` (+3 new).

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 2.1 | tests/test_api.py (+6 new: entries display units, entries bmi with height, summary display units, summary None-empty, rewards threshold units, WeightIn unknown-key 422; 2 contract updates) | Integration | suite (65) | 6 failures: missing `lb`/`stone`/`stone_lb`/`bmi` keys (KeyError) + unknown weight key not rejected (201 != 422) | 73 passed (6 new + 2 updated contracts) | exact kg↔lb factor (×2.2046226218), stone decomposition, BMI 175cm, None-safe empty summary, rewards 10%/50% thresholds, unknown-key 422 | `_weight_view` + `_summary_view` helpers centralize derivation; canonical `*_kg` keys untouched so the SPA keeps its existing contract |
| 2.2 | tests/test_scheduler.py (+3 new: tick-sourced `sent_at` via `_local_now` decoy monkeypatch, DST repeated hour single-send, DST skipped time fires on next tick) | Integration | suite (73) | 1 genuine failure (stored `sent_at` = decoy, not the tick's local time) + 1 test-authoring bug fixed during RED (23:59 tick legitimately fires tip/reminder → `count == 2`, only exercise deduped); 2 DST regressions green immediately (behavior already correct by construction) | 74 passed | monkeypatched `database._local_now` decoy proves the tick's timestamp wins; repeated 01:30 wall time on same local date sends once; 02:30 skipped → fires at 03:00 same date | `mark_notification_sent` gains `sent_at: Optional[str] = None` param; scheduler passes `now.strftime` |

## Work Unit Evidence

| Evidence | Required value |
|----------|----------------|
| Focused test command and exact result | `.venv/bin/python -m pytest tests/test_api.py tests/test_scheduler.py` → **38 passed** (was 32 before slice); full suite `.venv/bin/python -m pytest -q` → **74 passed in 0.59s** |
| Runtime harness command/scenario and exact result | Real uvicorn boot (`WEIGHT_LOSS_DB=/tmp/... WEIGHT_LOSS_VAPID_KEYS=/tmp/... uvicorn main:app --port 8793`): PUT settings height=175/target=80 → POST 100kg, 95kg → GET `/api/weight` 200 (entry: `{weight_kg:95, lb:209.439, stone:14, stone_lb:13.439, bmi:31.020}`; summary baseline/current/lost/target/remaining with `_lb`/`_stone`/`_stone_lb`, `_bmi` only on baseline/current/target) → GET `/api/rewards` 200 (active 10%/25% with `threshold_lb`/`threshold_stone`/`threshold_stone_lb`/`earned_at`, next 50% with display units) → POST `/api/weight` with unknown key `units` → **422** |
| Rollback boundary | Revert branch `slice-2-backend` to `main` (PR #1 content). Slice-2 files: `routes.py` (display serialization + `WeightIn` strictness), `scheduler.py`, `database.py` (`mark_notification_sent` signature), `tests/test_api.py`, `tests/test_scheduler.py`. Frontend untouched — slice 3 renders the new fields. |

## Deviations from Design

1. **`_weight_view`/`_summary_view` helpers in routes.py** — the design places display construction in units.py (`weight_display` already exists there and is reused); routes adds thin dict serializers. No logic duplication, `units.weight_display` remains the single source of truth.
2. **BMI field policy**: entries + summary real weights (baseline/current/target) carry `bmi`; deltas (lost/remaining) carry multi-unit only — the spec requires BMI only for the current summary/history/tooltip, and BMI of a delta is meaningless. Documented in `_summary_view` docstring; pinned by tests (no `lost_bmi`/`remaining_bmi` keys).
3. **Two pre-existing rewards tests updated** (`test_rewards_checkpoints_earned_via_upserts`, `test_rewards_regression_revokes_checkpoints`): exact-equality `next_checkpoint == {"percent": …, "threshold_kg": …}` assertions extended to the new additive keys — contract extension, not relaxation (per design's "existing step/default assertions must change").
4. **`database.py` touched in 2.2** (tasks.md says "update scheduler.py ~100 lines"): the `sent_at` override parameter lives on `mark_notification_sent`; the scheduler alone cannot force its tick time into the DB layer otherwise.

## Issues Found

1. **Latent slice-1 bug — persisted VAPID load path crashes (out of slice scope, flagged):** py_vapid 1.9.4 `Vapid.from_raw` crashes with `TypeError: can only concatenate str (not "bytes") to str` on a str private key loaded from `vapid_keys.json` (`notifications._vapid_from_payload`). Fresh-generate path works, so the first boot is fine but **every subsequent boot with persisted keys crashes**. Reproduced 3× against a real server; fix verified as `Vapid.from_raw(payload["private_key"].encode("ascii"))`. Not fixed here — notifications.py is not in slice-2 scope; recommend a small follow-up (slice 3/4 or dedicated PR) with a regression test.
2. Pyright LSP diagnostics (17) remain environment noise (`.venv` unresolved; `pyrightconfig.json` is 4.1) — runtime imports prove fine (74 passed).

## Status

Slice 2 complete: 2/2 tasks (2.1, 2.2). PR #2 open for review (not merged — orchestrator/verify decides). next_recommended: sdd-apply slice 3 (frontend) after PR #2 merge, or sdd-verify first.
