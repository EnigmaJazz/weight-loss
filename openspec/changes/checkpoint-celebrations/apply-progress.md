# Apply Progress: Checkpoint Celebration Notifications

**Change**: checkpoint-celebrations
**Mode**: Strict TDD (strict_tdd: true in openspec/config.yaml, pytest runner available)
**Artifact store**: OpenSpec
**Date**: 2026-08-08
**Status**: All 8 tasks complete (Phases 1-3), suite green, ready for verify

## Delivery Context

- Branch: `feat/checkpoint-celebrations` (created from main @ 7e96216)
- Workload decision: `auto-chain` forecast, Medium risk, "Decision needed before apply: No" — single PR confirmed by orchestrator (tasks.md unit table: 1 unit → PR 1)
- Rollback boundary: revert the 5 route fire calls + `_celebrate_if_earned` (routes.py) + `pick_celebration`/`send_celebration` (notifications.py) + `CELEBRATION_MESSAGES` (constants.py) + `newly_earned_checkpoints` (rewards.py); delete `tests/test_celebrations.py`. No schema change, no persisted celebration state — already-sent pushes are inert.

## Completed Tasks

- [x] 1.1 RED — `tests/test_rewards.py`: units for `newly_earned_checkpoints` (single earn, batched, idempotent, revoke-only, same-event revoke+re-earn, revoke+earn of a different percent, duplicate-percent safety, empty→empty)
- [x] 1.2 GREEN — `rewards.py`: `newly_earned_checkpoints(before, after)` set-difference helper; `Any` added to typing import
- [x] 1.3 RED — `tests/test_notifications.py`: `pick_celebration` pool contract, seeded determinism, interpolation, `send_celebration` notif_type capture
- [x] 1.4 GREEN — `constants.py`: `CELEBRATION_MESSAGES` (6 variants); `notifications.py`: `pick_celebration(percent, rng=None)` + `send_celebration(subscriptions, percent, vapid)`
- [x] 2.1 RED — `tests/test_celebrations.py` (new): 14 integration scenarios via `stub_push`
- [x] 2.2 GREEN — `routes.py`: `_celebrate_if_earned` helper + `request: Request` + before/after/celebrate in all 5 earn-capable routes
- [x] 3.1 Audit — full suite green; zero existing stub_push tests needed updates
- [x] 3.2 Full verification — pytest 404, pyright 0 errors, node 96, static/ untouched, git clean

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | `tests/test_rewards.py` | Unit | ✅ 24/24 | ✅ Written | ✅ Passed (ImportError → 32) | ✅ 8 cases | ➖ None needed (matches design) |
| 1.2 | `tests/test_rewards.py` | Unit | N/A (new behavior) | ✅ Written (1.1) | ✅ 32 passed | ✅ covered in 1.1 | ➖ None needed |
| 1.3 | `tests/test_notifications.py` | Unit | ✅ 8/8 | ✅ Written | ✅ Passed (4 failed → 12) | ✅ 3 cases | ✅ removed redundant asyncio markers |
| 1.4 | `tests/test_notifications.py` | Unit | N/A (new behavior) | ✅ Written (1.3) | ✅ 12 passed | ✅ covered in 1.3 | ✅ title+body interpolation fix (see deviations) |
| 2.1 | `tests/test_celebrations.py` | Integration | ✅ 378 full suite | ✅ Written | ✅ Passed (11 failed → 14) | ✅ 14 scenarios | ✅ fixed helper 200/201 status |
| 2.2 | `tests/test_celebrations.py` | Integration | ✅ 378 full suite | ✅ Written (2.1) | ✅ 14 passed | ✅ covered in 2.1 | ➖ None needed |
| 3.1 | full suite | — | ✅ 378 | N/A (audit) | ✅ 404 passed | N/A | N/A |
| 3.2 | pyright + node + git | — | N/A | N/A | ✅ 0 errors / 96 pass / clean | N/A | N/A |

## Work Unit Evidence

| Evidence | Required value |
|---|---|
| Focused test command and exact result | `.venv/bin/python -m pytest tests/test_celebrations.py -q` → 14 passed; unit files `tests/test_rewards.py` (32) + `tests/test_notifications.py` (12) |
| Runtime harness command/scenario and exact result | In-process httpx ASGITransport via conftest (`auth_client`/`pair` + `stub_push`); 14 integration scenarios exercised the real route→DB→reconcile→diff→send path. No live network: `stub_push` guarantees no real push (fire-and-forget, no live-verify surface) — explicit N/A for live E2E |
| Rollback boundary | Revert fire calls in 5 routes + `_celebrate_if_earned` + `pick_celebration`/`send_celebration` + `CELEBRATION_MESSAGES` + `newly_earned_checkpoints`; delete `tests/test_celebrations.py`; no schema/persisted state |

## Files Changed

| File | Action | What Was Done |
|------|--------|---------------|
| `rewards.py` | Modified | +`newly_earned_checkpoints(before, after)` pure set-difference by `checkpoint_percent`; `Any` added to typing import |
| `constants.py` | Modified | +`CELEBRATION_MESSAGES` standalone tuple (6 (title, body) variants, `{percent}` placeholder, no emoji in titles, second-person celebratory tone) |
| `notifications.py` | Modified | +`pick_celebration(percent, rng=None)` (seeded-deterministic, interpolates `{percent}` in title AND body); +`send_celebration(subscriptions, percent, vapid)` → `send_to_all(..., notif_type="checkpoint")` |
| `routes.py` | Modified | +`_celebrate_if_earned(db, vapid, user_id, before, after)` (diff → top percent → `list_subscriptions` → `send_celebration`); `+request: Request` + before/after/celebrate in `complete_onboarding`, `upsert_weight`, `edit_weight`, `delete_weight`, `put_settings`; imports `Vapid`, `newly_earned_checkpoints` |
| `tests/test_celebrations.py` | Created | 14 integration scenarios via `stub_push`: upsert single/batched, idempotent, revoke-only, re-earn refire (`_local_now` patched), edit earn, edit 409, delete baseline-shift, delete revoke-only, settings target earn, theme-only, onboarding first-entry, zero-subs + no dedupe row, per-user isolation |
| `tests/test_rewards.py` | Modified | +8 pure-unit tests for the diff helper (incl. duplicate-percent safety) |
| `tests/test_notifications.py` | Modified | +4 tests: pool contract, seeded determinism, interpolation, `send_celebration` capture |

## Audit Outcome (task 3.1)

All 5 audited stub_push tests passed unchanged — zero churn confirmed:

- `test_api.py::test_push_test_sends_to_all` ✅ (auth_client has no weight entries → no checkpoint possible)
- `test_api.py::test_manual_notify_endpoints` ✅ (asserts exactly 3 pushes `["tip","reminder","exercise"]`, no checkpoint)
- `test_scheduler.py::test_api_disabled_schedule_is_skipped` ✅ (asserts `stub_push == []`; auth_client has no entries → PUT settings diff empty)
- `test_user_isolation.py::test_push_test_targets_only_own_subscriptions` ✅ (pair has no entries)
- `test_user_isolation.py::test_manual_notify_targets_only_own_subscriptions` ✅
- `test_onboarding.py` earn tests ✅ (never subscribe; stub_push not referenced)

Design audit prediction (design.md line 110) held exactly: no test subscribes AND earns AND asserts stub_push concurrently. **No existing test was updated.**

## Test / Verification Counts

- Full suite: `.venv/bin/python -m pytest -q` → **404 passed** (baseline 378 + 26 new: 8 rewards + 4 notifications + 14 celebrations)
- Pyright: `.venv/bin/pyright` → **0 errors, 0 warnings, 0 informations**
- Frontend: `node --test tests/frontend/*.test.mjs` → **96 pass, 0 fail** (untouched, matches baseline)
- `git diff --stat main -- static/` → **empty** (zero frontend changes)
- `git status --short` → clean after commits (only change-folder artifacts committed as final commit)

## Commits

| Hash | Subject |
|------|---------|
| 1aa9fee | feat(rewards): add newly_earned_checkpoints diff helper and tests |
| 51ce7e9 | feat(notifications): add celebration message pool, picker, and sender |
| 7ebe841 | feat(routes): fire checkpoint celebration on earn-capable routes |
| (final) | docs(openspec): mark checkpoint-celebrations apply complete |

## Deviations from Design

1. **`pick_celebration` interpolates `{percent}` in BOTH title and body** — the design's pool includes one variant with the placeholder in the title (`"{percent}% — nice!"`), but the design's picker code only replaced it in the body, which would leak a literal `{percent}` into a user-facing push title. Interpolating both places is required for the design's own pool to render correctly and satisfies the spec ("returning (title, body) with {percent} interpolated"). Tests assert no `{percent}` appears anywhere in the returned message.

Everything else matches design.md exactly (helper signature `_celebrate_if_earned(db, vapid, user_id, before, after)` per §Interfaces; route wiring per the route table; audit per line 110).

## Issues Found

- None blocking. Test-helper fix during TDD: `_post_weight` asserted 201 but an idempotent re-POST correctly returns 200 (existing date → update) — helper now accepts both.
- Design inconsistency noted above (title placeholder) was the only design flaw discovered.

## Status

8/8 tasks complete. Ready for verify (sdd-verify).
