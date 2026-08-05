# Archive Report: notification-schedule-disable

**Change**: notification-schedule-disable
**Archived**: 2026-08-04
**Mode**: Strict TDD (active)
**Final verdict**: PASS — 3/3 requirements, 7/7 scenarios, 89 pytest + 6 node:test green, build_exit_code 0 per config

## Summary

Closed the notification-schedule disable gap end-to-end. The scheduler already treated `""` as disabled at the persistence layer; the API validator (`_valid_time`) rejected `""` with 422 and the SPA sent `null` for cleared time inputs (which restored defaults instead of disabling). The fix carried the existing empty-string sentinel through the two ingress points:

- `routes.py` `_valid_time`: accepts `""` as the disabled sentinel, keeps `None` pass-through and strict `HH:MM` validation; docstring documents `""` = disabled vs `null` = restore-default.
- `static/app.js` `saveSettings.time()`: sends `""` for cleared inputs instead of `null`.
- `static/index.html`: "leave blank to disable" hints on the three time labels.
- `database.py` and `scheduler.py`: untouched — both already implemented the contract.

Also handled during this change: `.gga` (Gentle AI provider config) added to `.gitignore` and untracked per maintainer decision.

## Evidence

- Full suite: `.venv/bin/python -m pytest -q` → 89 passed
- Frontend formatter: `node --test tests/frontend/weight-label.test.mjs` → 6/6
- SPA runtime harness: 2/2 against production `static/app.js`
- Delta suite: 14 passed
- Runtime: httpx ASGITransport PUT `""` → 200 → GET `""`; disabled schedule 0 sends + no dedupe key; live uvicorn round-trip verified
- Build: `build_command: ""` per config, `build_exit_code: 0` (pyright env hang recorded as WARNING only)

## Delta Specs Synced

- `local-time-notifications`: ADDED `Notification Schedule Settings API` requirement (3 scenarios), `Notification Schedule Settings Form` requirement, SPA scenarios; UPDATED scheduler disabled scenario to reflect API-persisted `""`. Additive merge — no destructive delta.

## Task Completion

- 8/8 tasks complete; 3.2-style conditional deferral not applicable (no optional polish tasks in this change).

## Rollback

- Revert commit(s) of the feature + tests to restore prior behavior (validator rejects `""` again). `.gga` gitignore change is separate and inert.

## Follow-ups (non-blocking)

- Pyright must run in CI/normal env (hangs with exit 124 in the dev environment).
- None other recorded.
