# Tasks: Disable Notification Schedules

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 60–90, including tests |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Persist and skip disabled schedules end-to-end | PR 1 | `.venv/bin/python -m pytest tests/test_api.py tests/test_scheduler.py` | `httpx.ASGITransport` with `tests/conftest.py` fixtures; manual SPA smoke | Revert `routes.py`, `static/app.js`, and related tests |

## Phase 1: RED — Regression Tests

- [x] 1.1 In `tests/test_api.py`, add async API tests for empty-string PUT/GET round-trip (all time fields), `null` restore-default, strict valid boundaries, and invalid non-empty/whitespace values returning 422 without mutation; run the focused pytest command.
- [x] 1.2 In `tests/test_scheduler.py`, add the API-to-scheduler regression: PUT `tip_time: ""`, run `run_due_checks` after the former due time, and assert zero sends plus no `(date, tip)` `notifications_sent` key; use the existing stub-push/conftest harness.

## Phase 2: GREEN — Minimal Production Changes

- [x] 2.1 In `routes.py`, update `_valid_time` to pass through `None` and `""`, retain strict `HH:MM` validation for non-empty values, and document `""` = disable versus `null` = restore default; make Phase 1 tests pass.
- [x] 2.2 In `static/app.js`, change `saveSettings.time()` so a cleared input serializes as `""`; rely on API contract tests and a manual/browser settings smoke because no SPA JS harness is in scope (the existing node:test covers formatting only).

## Phase 3: TRIANGULATE — Integration Verification

- [x] 3.1 Run `.venv/bin/python -m pytest` and verify API persistence, null semantics, invalid-input immutability, and scheduler no-send/no-dedupe behavior; exercise the in-process ASGI harness.
- [x] 3.2 Manually clear a browser time input, save, reload, and confirm it remains empty; confirm existing `tests/frontend/weight-label.test.mjs` remains unchanged because it does not cover SPA serialization.

## Phase 4: REFACTOR — Polish and Release Gate

- [x] 4.1 Keep the change minimal; optionally add "Leave blank to disable" to the three time labels in `static/index.html` if review remains within budget, otherwise record the hint as deferred.
- [x] 4.2 Confirm the delta spec documents `""` versus `null`, review the diff/stat, and create one conventional commit (for example `fix(notifications): allow disabling schedules`) with no AI attribution; rollback is a single commit revert.
