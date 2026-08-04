# Exploration: Notification schedules cannot be disabled through the API

Change: `notification-schedule-disable`
Phase: sdd-explore
Date: 2026-08-04

## Current State

The scheduler already treats an empty string as "disabled", but the API/UI path can
never produce one. Full trace of the settings path:

1. **Validation (routes.py:51-60)** — `_valid_time` accepts `None` (returns it) or a
   strict `HH:MM` string; `""` fails the `split(":")` length check and raises → 422.
   `SettingsIn` (routes.py:108-121) applies `_valid_time` via `validate_time` to the
   three time fields, each `Optional[str] = None`.
2. **Route (routes.py:276-284)** — `put_settings` dumps `SettingsIn` with
   `exclude_unset=True` and calls `db.update_settings(updates)`.
3. **Storage (database.py:212-226)** — `update_settings` treats `value is None` as
   DELETE-the-row; any other value is upserted as a string. `""` is NOT `None`, so it
   would already be persisted correctly — the blocker is purely the validator in (1).
4. **Read-back (database.py:194-210)** — `_settings_from_conn` does
   `str(stored.get("tip_time", DEFAULT_SETTINGS["tip_time"]))`. A stored `""` is found
   by `.get` (the key exists) and survives the `str()` — no fallback to the default.
   A DELETEd row falls back to `DEFAULT_SETTINGS` (constants.py:28-35:
   tip "09:00", reminder "20:00", exercise "17:00").
5. **Consumption (scheduler.py:19-23)** — `_due_today` returns `False` for falsy
   schedules; `AppSettings.time_for` (models.py:66-73) returns the raw stored string.
   So `""` disables, exactly as the archived spec `local-time-notifications` requires
   ("an empty schedule MUST disable that type", LT-2 scenario "Schedule is disabled").

**Net gap**: `PUT /api/settings {"tip_time": ""}` → 422; `{"tip_time": null}` → row
deleted → default "09:00" restored. A client can only re-enable/change a schedule,
never turn it off. This is verify-report WARNING #2 (archived core-app change) and is
already recorded as a non-blocking carried-forward warning in `archive-report.md`.

**Confirmed live behavior** (read from code, not guessed):
- `"".split(":") == [""]` → `len(parts) != 2` → `ValueError` → 422. (routes.py:54-56)
- `update_settings({"tip_time": ""})` → `"" is not None` → `INSERT ... ON CONFLICT`
  stores `""`. (database.py:215-224)
- `_settings_from_conn` with row `("tip_time", "")` → `""`. (database.py:199)
- `_due_today(now, "")` → `not ""` → `False` → skipped, no dedupe key written.
  (scheduler.py:19-23, run_due_checks scheduler.py:32-34)

## Affected Areas

- `routes.py:51-60` (`_valid_time`) — the single blocker: must accept `""` as the
  disabled sentinel. Only caller is `SettingsIn.validate_time` (routes.py:118-121).
- `static/app.js:307-310` (`time()` helper in `saveSettings`) — currently maps an
  empty time input to `null` (→ DELETE → default restored). Must send `""` instead so
  clearing the input disables the notification. `renderSettings` (app.js:292-299)
  already renders `""` correctly via `?? ""`, so no read-side change.
- `static/index.html:58-63` — optional: hint text ("leave blank to disable") on the
  three `type="time"` inputs; not required for the fix.
- `tests/test_api.py` — new regression test(s) for the API contract (see inventory).
- `tests/test_scheduler.py` — optional integration test proving the full
  API → scheduler path; existing DB-level `""` tests (line 78) already pass and
  remain valid.
- No changes needed: `database.py` (persistence already correct), `constants.py`
  (`DEFAULT_SETTINGS` unchanged), `models.py` (`AppSettings` `str` fields already
  allow `""`), `scheduler.py` (semantics already correct and tested).

## Approaches

1. **Accept `""` as the disabled time value (recommended)** — change `_valid_time` to
   pass `""` through (`if not value: return value` handles both `None` and `""`), and
   change the SPA `time()` helper to return `""` for an empty input.
   - Pros: uses the exact sentinel the scheduler already implements and the spec
     already mandates (`""` = disabled) — one meaning across the whole stack; fully
     backward compatible (no current client sends `""` — it 422s today; `null` keeps
     its "clear → default" meaning); storage/schema/read-back already support it, so
     the diff is ~3 production lines + tests; GET round-trips `""` unchanged.
   - Cons: `null` for a time field still means "restore default", which is now
     asymmetric with `""` = "disable" — a footgun for future API clients (the SPA
     never sends `null` for times after the fix, so no real-world impact). Needs the
     SPA change to take effect for UI users.
   - Effort: Low (≈ 60-90 changed lines incl. tests).

2. **Normalize `null` → `""` for time fields in the route/validator** — treat a null
   time as disabled too, so the current SPA works without modification.
   - Pros: no SPA change required; the existing empty-input → `null` flow starts
     working.
   - Cons: silently changes the meaning of `null` on the three time fields (was
     "clear to default", becomes "disable") — a contract change with no migration
     path and no way left to restore a default time via the API; send-`null`/get-`""`
     asymmetry is worse than Approach 1 (the API says one thing and stores another);
     muddies `_valid_time`'s None-vs-empty distinction that other fields rely on.
   - Effort: Low-Medium (validator change only, but contract ambiguity).

3. **Explicit disabled flag / sentinel string (e.g. `"off"`)** — new setting keys or a
   non-`HH:MM` sentinel distinct from empty.
   - Pros: unambiguous; self-documenting in the API.
   - Cons: new storage surface (schema/keys/`AppSettings`/serialization), more SPA
     logic, more tests — all to express something `""` already expresses end-to-end;
     diverges from the shipped and spec'd `""` semantics; overkill for a single-user
     app.
   - Effort: Medium-High.

4. **SPA omits empty time fields instead of sending them** — `exclude_unset`-style
   omission means "keep current", so clearing an input would NOT disable; it is
   orthogonal to the disable problem. Rejected.

## Recommendation

**Approach 1**: accept `""` as the disabled sentinel in `_valid_time` and make the SPA
send `""` for a cleared time input. It closes the gap with the smallest diff because
every layer below the validator already implements `""` = disabled, it matches the
archived spec's LT-2 wording exactly, and it changes no existing behavior. Record the
`null` = "restore default" vs `""` = "disable" distinction explicitly in the proposal
so the API contract is documented, not accidental.

Suggested minimal implementation shape:

```python
def _valid_time(value: Optional[str]) -> Optional[str]:
    if not value:          # None = clear (null) -> default; "" = disabled
        return value
    ...
```

## API Contract After the Change

- `PUT /api/settings {"tip_time": ""}` → 200, response `"tip_time": ""`; persisted as
  a `settings` row with value `""`; scheduler skips tip (no send, no dedupe key).
- `PUT /api/settings {"tip_time": null}` → 200, row deleted, default `"09:00"`
  restored (unchanged from today).
- `PUT /api/settings {"tip_time": "25:99"}` / `"not-a-time"` → 422 (unchanged).
- `GET /api/settings` returns `""` for a disabled type (round-trips unchanged).

## Test Inventory

New tests (strict TDD — RED first):
- `tests/test_api.py::test_settings_disable_time_with_empty_string` — PUT
  `{"tip_time": ""}` → 200, body `tip_time == ""`; GET confirms persistence; the
  other two times keep their defaults. (Core regression for the API acceptance.)
- `tests/test_api.py` (or `test_scheduler.py`) integration test — PUT `""` via the
  client, then `run_due_checks` at a time that would otherwise fire → 0 sends and no
  `notifications_sent` row for that type/date. Proves the full API → scheduler path.
- Optional: extend `test_settings_bad_time_rejected` with a whitespace-only string
  (still 422) to pin the boundary.

Existing tests that must stay green and need NO change:
- `test_settings_get_returns_defaults` (test_api.py:24) — defaults unchanged.
- `test_settings_put_partial_update` (test_api.py:36), `test_settings_clear_override_with_null`
  (test_api.py:48, target_weight only), `test_settings_bad_time_rejected` (test_api.py:56),
  `test_settings_retired_key_rejected` (test_api.py:64), `test_settings_save_height`,
  `test_settings_nonpositive_height_rejected` — all assert behavior the change
  preserves.
- `test_scheduler.py` — `test_due_checks_respects_scheduled_times` (line 78) already
  exercises DB-level `""` disable; DST/dedupe tests unaffected.
- `tests/conftest.py` harness — no change; existing `app`/`client` fixtures and the
  `stub_push` autouse fixture cover the new integration test as-is.

## UI-Side Impact

- `static/app.js`: one-line change in the `time()` helper (return `""`, not `null`,
  for empty input). `renderSettings` already round-trips `""` (`?? ""`).
- Times are only rendered in the settings form (inputs `type="time"`); no other time
  display/formatting exists in the SPA, so no formatting contract changes.
- Optional polish: hint text on the time labels ("leave blank to disable") so the
  empty-input behavior is discoverable.

## Risks

- **WARNING (contract documentation)**: after the fix, `""` = disabled but `null` =
  restore default for the same field. If the proposal phase does not record this
  distinction, a future client may send `null` expecting "off" and silently re-enable
  the default schedule. Mitigation: document in the delta spec/proposal; the SPA never
  sends `null` for times.
- **WARNING (UI behavior)**: with `type="time"` inputs, some browsers render an empty
  value as "invalid" styling and clearing is only possible via the browser's clear
  affordance; the fix works, but the UX is only as discoverable as the hint text we
  add.
- **INFO (spec home)**: the API/UI persistence requirement has no explicit home today.
  `local-time-notifications` LT-2 covers scheduler semantics only; `weight-tracking`
  "Settings Contract" covers the settings API/UI. The delta spec should ADD the
  persistence requirement (recommend `local-time-notifications`, since it owns
  schedule semantics) rather than leaving it implicit.

## Ready for Proposal

**Yes.** The gap is precisely mapped, the fix is minimal and backward compatible, and
the test plan is enumerated. The orchestrator should tell the user: "Notification
schedules can be disabled by accepting an empty time string end-to-end (~3 production
lines + 2-3 tests); `null` keeps meaning 'restore default'."
