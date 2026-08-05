# Design: Disable Notification Schedules

## Technical Approach

Carry the existing empty-string sentinel through the two blocking ingress points: FastAPI validation and SPA serialization. The database and scheduler already implement the delta specification's `""` = disabled behavior, so they remain unchanged. Preserve `null` as the distinct restore-default operation.

## Architecture Decisions

| Decision | Choice | Alternatives considered | Rationale |
|---|---|---|---|
| Disabled representation | Reuse `""` end-to-end | Boolean flags, an `"off"` value, schema changes | It matches shipped scheduler behavior, round-trips through existing storage, and minimizes the change. |
| Null semantics | Keep `null` as delete-override/restore-default | Normalize `null` to `""` | Changing `null` would break compatibility and remove the API operation that restores defaults. |
| Lower layers | Do not modify persistence or scheduler logic | Normalize in the database or add scheduler branches | Both layers already implement the required contract; changing them would add risk without behavior. |

## Data Flow

    cleared input → time() returns "" → PUT validator returns ""
        → settings upsert → GET returns "" → renderSettings displays empty
        → time_for() returns "" → _due_today() is false → no send/dedupe key

`null` follows a separate path: validator pass-through → settings-row deletion → configured default on read.

## File Changes

| File | Action | Description |
|---|---|---|
| `routes.py` | Modify | Make `_valid_time` return both `None` and `""` unchanged before strict `HH:MM` validation. Add a docstring stating `""` disables and `None` (JSON `null`) restores the default. `SettingsIn.validate_time` remains unchanged because it already delegates all three fields to `_valid_time`. |
| `static/app.js` | Modify | In `saveSettings.time()`, replace the empty-to-`null` ternary with `return v;`; the trimmed empty input is therefore submitted as `""`. `renderSettings` already preserves `""` through `s.field ?? ""`. |
| `tests/test_api.py` | Modify | Add API contract and boundary regressions. |
| `tests/test_scheduler.py` | Modify | Add the API-to-scheduler disabled-path regression. |
| `database.py` | No change | `settings.value` is `TEXT NOT NULL`; `update_settings` deletes only `None` and upserts `""`, while `_settings_from_conn` finds and returns the stored empty value. No schema change. |
| `scheduler.py` | No change | `_due_today` rejects falsy schedules before dedupe lookup/send/marking. |

`static/index.html` needs no functional change. A copy-only hint, “Leave blank to disable,” is recommended for discoverability but remains outside this focused fix.

## Interfaces / Contracts

Each notification time accepts strict `HH:MM`, `""`, or `null`. `""` persists and disables; `null` removes the override; every other non-empty value returns 422 without changing storage. No new types, endpoints, or database structures are introduced.

## Testing Strategy

| Layer | Planned regression |
|---|---|
| API integration | `test_settings_disable_time_with_empty_string`: parameterize the three fields; PUT/GET must round-trip `""` and leave other defaults intact. |
| API integration | Add notification-time `null` restore-default coverage and assert invalid input leaves the prior value unchanged. |
| Boundaries | Accept `00:00` and `23:59`; reject `24:00`, `23:60`, unpadded, malformed, and whitespace-only values with 422. |
| Scheduler integration | Disable `tip_time` through the API, run `run_due_checks` after its former due time, and assert zero sends, zero count, and no `(date, tip)` dedupe key. |
| SPA | No browser E2E harness exists; verify the focused serialization change and existing `?? ""` render path during review. |

Existing tests that must remain green: `test_settings_get_returns_defaults`, `test_settings_put_partial_update`, `test_settings_clear_override_with_null`, `test_settings_bad_time_rejected`, `test_settings_retired_key_rejected`, `test_settings_save_height`, `test_settings_nonpositive_height_rejected`, `test_due_checks_fire_once_then_dedupe`, `test_due_checks_respects_scheduled_times`, `test_due_checks_with_no_subscriptions`, `test_scheduler_persists_sent_at_from_tick`, `test_dst_repeated_hour_sends_once`, and `test_dst_skipped_time_fires_on_next_tick`.

## Threat Matrix

| Boundary | Applicability | Reason |
|---|---|---|
| Documentation-like paths | N/A | No file classification or execution boundary. |
| Git repository selection | N/A | No Git invocation. |
| Commit state | N/A | No commit automation. |
| Push state | N/A | No push automation. |
| PR commands | N/A | No PR command composition. |

## Migration / Rollout

No migration or feature flag is required. Roll out atomically with tests. Roll back with a single commit revert; future API/SPA behavior returns to rejecting/restoring defaults for cleared values. Existing persisted `""` rows remain valid and disabled until replaced or reset with `null`.

## Open Questions

None.
