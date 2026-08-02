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
