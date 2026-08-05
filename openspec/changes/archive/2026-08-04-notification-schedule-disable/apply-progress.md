# Apply Progress: notification-schedule-disable

**Change**: notification-schedule-disable
**Branch**: `fix/schedule-disable` (from `main`; single PR, no chain — forecast Low)
**Mode**: Strict TDD (active, resolved from openspec/config.yaml `strict_tdd: true`)
**Status**: 8/8 tasks complete (1.1, 1.2, 2.1, 2.2, 3.1, 3.2, 4.1, 4.2)
**Test counts**: 76 passing at start → **89 passing at end** (all green; +13 new) + 6 node:test (unchanged)

## Completed Tasks

- [x] 1.1 API contract tests — `tests/test_api.py`: parameterized empty-string PUT/GET round-trip for all three time fields, `null` restore-default, strict `00:00`/`23:59` boundaries, and invalid non-empty/whitespace values returning 422 without mutation.
- [x] 1.2 API→scheduler regression — `tests/test_scheduler.py::test_api_disabled_schedule_is_skipped`: PUT `tip_time: ""`, `run_due_checks` at the former due time → zero sends, zero count, no `(date, tip)` dedupe key; re-enable proves the skip came from the disable.
- [x] 2.1 `routes.py` — `_valid_time` passes `None` and `""` through unchanged, retains strict `HH:MM` validation for every other value, and its docstring documents `""` = disable vs `null` = restore default. `SettingsIn.validate_time` unchanged (already delegates all three fields).
- [x] 2.2 `static/app.js` — `saveSettings.time()` returns the trimmed value as-is; a cleared input serializes as `""` (never `null`). `renderSettings` already renders `""` via `s.field ?? ""`.
- [x] 3.1 Full-suite + in-process ASGI verification (see Work Unit Evidence).
- [x] 3.2 SPA smoke — `node --check static/app.js` OK; `tests/frontend/weight-label.test.mjs` unchanged (6/6 pass); live uvicorn round-trip proven; real-browser click-through not possible in this environment (core-app precedent: code-path + live smoke is the check).
- [x] 4.1 UX hint — "leave blank to disable" appended to the three time labels in `static/index.html` (diff stayed at 117 changed lines, far under the 400-line budget, so the optional hint was implemented, not deferred).
- [x] 4.2 Release gate — delta spec already documents `""` vs `null` (spec.md ADDED requirement); diff/stat reviewed (111+/6−); one conventional commit, no AI attribution (see Commits).

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | tests/test_api.py (12 new: 3 round-trip params, 1 null-restore, 2 boundaries, 6 invalid) | Integration | suite (76) | 3 failures: `PUT {field: ""}` → 422 (round-trip params); null/boundary/invalid cases green immediately as contract pins | 48 passed on the focused files (was 44+4 RED) | all three time fields; `00:00`/`23:59` accepted; `24:00`/`23:60`/unpadded/malformed/whitespace → 422 with stored value unchanged | `_valid_time` docstring documents the `""`/`null` asymmetry; `if not value: return value` covers both falsy sentinels |
| 1.2 | tests/test_scheduler.py::test_api_disabled_schedule_is_skipped | Integration | suite (76) | 1 failure: `PUT tip_time: ""` → 422 before the scheduler ever ran | 48 passed on focused files; live uvicorn boot PUT `""` → 200, GET `""` | re-enable `"09:00"` through the API → the SAME tick fires tip (1 send, dedupe key written), proving the skip was the disable, not a broken scheduler | none needed — test already minimal; reuses conftest `client`/`app`/`stub_push` |
| 2.1+2.2 | (production) | Unit/Integration | suite (76) | N/A — production changes driven by the RED tests above | 89 passed full suite; `node --check static/app.js` OK | covered by 1.1/1.2 triangulation matrix | comment on `time()` documents why `""` and not `null` |

RED note: the empty-string round-trip tests are the only genuinely failing tests pre-change (`""` → 422 today). The `null`-restore, boundary, and invalid-value tests passed before AND after — they pin already-correct contract paths and would catch regressions (e.g. accidentally normalizing `null` to `""`).

## Work Unit Evidence

| Evidence | Required value |
|----------|----------------|
| Focused test command and exact result | `.venv/bin/python -m pytest tests/test_api.py tests/test_scheduler.py` → RED: 4 failed (empty-string round-trip ×3 + scheduler), 44 passed; GREEN: **48 passed** |
| Runtime harness command/scenario and exact result | In-process httpx ASGITransport (conftest `client`): `PUT /api/settings {"tip_time": ""}` → 200 with `"tip_time": ""`, GET round-trips `""`; `run_due_checks` at 10:00 with tip disabled → `count == 0`, `stub_push == []`, no `(date, tip)` key; re-enable → `count == 1`. **Live uvicorn boot** (tmp DB/VAPID, port 8791): PUT `""` → 200 + body `tip_time:""`; GET → `tip_time:""`; PUT `null` → 200 → GET `tip_time:"09:00"` (default restored); PUT `"25:99"` → 422. Full suite `.venv/bin/python -m pytest -q` → **89 passed in 0.60s**; `node --test tests/frontend/weight-label.test.mjs` → **6 passed** |
| Rollback boundary | Single code commit `fix(routes): accept empty schedule to disable notifications` (revert removes routes.py, static/app.js, static/index.html, tests/test_api.py, tests/test_scheduler.py changes; no schema/migration impact — existing persisted `""` rows stay valid and disabled). Docs commit is separate and inert. |

## Commits

| Hash | Message |
|------|---------|
| (see git log) | `fix(routes): accept empty schedule to disable notifications` — production + tests + hint |
| (see git log) | `docs(openspec): record notification-schedule-disable apply progress` — tasks.md checkboxes + apply-progress.md |

## Deviations from Design

None — implementation matches design. Both design-prescribed changes were applied exactly (`_valid_time` pass-through + docstring; `time()` ternary → `return v`), lower layers (database.py, scheduler.py) untouched as designed, and `SettingsIn.validate_time` confirmed unchanged.

## Issues Found

1. **Estimated vs actual diff**: tasks forecast 60–90 changed lines; actual code diff is 111+/6− (5 files) + ~100 lines of SDD docs. Still trivially under the 400-line budget — no chain needed. The extra lines are the broader boundary/immutability test matrix the design called for.
2. **Pre-existing `.gga` modification** (not mine, not committed): `PROVIDER="opencode"` → `PROVIDER="opencode:opencode-go/deepseek-v4-flash"` — environment provider pointer, left untouched.
3. **node --test directory target**: `node --test tests/frontend/` fails in node v26 ("Cannot find module"); the file target `node --test tests/frontend/weight-label.test.mjs` works (6/6). Recorded so verify/CI uses the file target.
4. **Real-browser click-through not executable in this environment** — the SPA serialization change is a one-line ternary swap; verified via `node --check`, the API contract tests, the live uvicorn round-trip, and code-path inspection of `time()`/`renderSettings` (`?? ""` renders the disabled `""` as an empty input). Same precedent as core-app slice 3.

## Discoveries Worth Persisting

- The `""` = disable vs `null` = restore-default asymmetry is now explicit in the delta spec AND the `_valid_time` docstring — future API clients have the contract documented at both the spec and code level.
- Lower layers needed zero changes, confirming the exploration's core finding: the validator was the single blocker; persistence, read-back, and scheduler already implement `""` = disabled.

## Status

8/8 tasks complete. **89/89 pytest + 6/6 node tests green.** Branch `fix/schedule-disable` ready for push/PR (orchestrator-owned). next_recommended: sdd-verify.
