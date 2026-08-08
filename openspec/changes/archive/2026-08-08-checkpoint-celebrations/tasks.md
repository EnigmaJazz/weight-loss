# Tasks: Checkpoint Celebration Notifications

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~300-350 (prod ~80, tests ~250) |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: stacked-to-main
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Helpers + route wiring + tests, end-to-end | PR 1 | `.venv/bin/python -m pytest -q` | In-process httpx ASGITransport via conftest; stub_push guarantees no real push (fire-and-forget, no live-verify surface) | Revert fire calls in 5 routes + `_celebrate_if_earned` + helpers + `CELEBRATION_MESSAGES`; delete `tests/test_celebrations.py`; no schema/persisted state |

## Phase 1: Foundation (pure helpers, RED → GREEN)

- [x] 1.1 RED — `tests/test_rewards.py`: units for `newly_earned_checkpoints` — single earn → {25}; idempotent re-POST → []; revoke-only → []; same-event revoke+re-earn → []; batched {10,25,50}; empty→empty (spec scenarios 1-4)
- [x] 1.2 GREEN — `rewards.py`: add `newly_earned_checkpoints(before, after)` set-difference helper; add `Any` to typing import. Verify: `pytest tests/test_rewards.py -q`
- [x] 1.3 RED — `tests/test_notifications.py`: `pick_celebration` — seeded determinism (same seed+percent → identical); `{percent}` interpolation (25 → "25%", no literal placeholder); pool ≥3, all contain `{percent}`
- [x] 1.4 GREEN — `constants.py`: `CELEBRATION_MESSAGES` tuple (6 style-matched messages); `notifications.py`: `pick_celebration(percent, rng=None)` + `send_celebration(subscriptions, percent, vapid)` → `send_to_all(..., notif_type="checkpoint")`; import pool. Verify: `pytest tests/test_notifications.py -q`

## Phase 2: Core Implementation (route wiring, RED → GREEN)

- [x] 2.1 RED — `tests/test_celebrations.py` (new): integration suite via `stub_push` — upsert single earn→1 push names 10; batched {10,25,50}→1 names 50; idempotent re-POST→0; revoke-only→0; re-earn refire→names 25; edit earn→1; edit 409→0; delete baseline-shift→names 50; delete revoke-only→0; settings target earn→1; theme-only→0; onboarding first-entry→1 top; zero-subs→0 + no dedupe row; per-user isolation (alice earns+subs, bob subs). Threshold math: baseline 100/target 80 → 10%=98, 25%=95, 50%=90
- [x] 2.2 GREEN — `routes.py`: `_celebrate_if_earned` helper (diff→top percent→subs→send); `+request: Request` + before/after/celebrate after successful mutate in `complete_onboarding` (751), `upsert_weight` (783), `edit_weight` (800, raise 409/404 before celebrate), `delete_weight` (828), `put_settings` (1051); import helper. Verify: `pytest tests/test_celebrations.py -q`

## Phase 3: Audit & Verification

- [x] 3.1 Audit existing stub_push-asserting tests: `test_api.py::test_push_test_sends_to_all`, `::test_manual_notify_endpoints`; `test_scheduler.py::test_api_disabled_schedule_is_skipped`; `test_user_isolation.py::test_push_test_targets_only_own_subscriptions`, `::test_manual_notify_targets_only_own_subscriptions`; `test_onboarding.py` earn tests — none subscribes+earns concurrently (auth_client/pair have no entries; tip_time is non-reward), expect zero churn; if any failure shows an unexpected checkpoint push, update that test to expect `notif_type=="checkpoint"` (design audit line 110)
- [x] 3.2 Full suite: `.venv/bin/python -m pytest -q` all green; `.venv/bin/pyright` clean; confirm `git diff --stat static/` empty (zero frontend changes)
