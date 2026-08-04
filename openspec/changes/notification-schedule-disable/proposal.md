# Proposal: Disable Notification Schedules

## Intent

Allow a user to disable any scheduled notification by clearing its time. The scheduler already honors an empty schedule, but API validation and the SPA currently prevent that value from being persisted.

## Scope

### In Scope
- Accept `""` for each notification time in `PUT /api/settings` as the disabled-schedule sentinel.
- Send `""` from cleared SPA time inputs so disabled schedules round-trip through the API.
- Add strict-TDD regression coverage for API persistence and the disabled scheduler path.
- Document the time-field API contract in the notification schedule specification.

### Out of Scope
- New notification types or changes to default notification times.
- A schedule-editor redesign, browser-specific input UX work, or database/schema refactoring.
- Changing `null` semantics or scheduler/deduplication behavior.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `local-time-notifications`: define API/UI persistence and round-trip semantics for disabled (`""`) notification schedules.

## Approach

Use the existing empty-string sentinel end-to-end. Update `routes.py` validation to return `""` unchanged, and update the SPA time helper to submit `""` rather than `null` for an empty input. Preserve the deliberate asymmetry: `""` disables a schedule; `null` deletes its override and restores the default. Invalid non-empty time strings remain rejected.

## Key Decisions and Tradeoffs

- Reuse the scheduler's shipped and specified sentinel rather than introduce flags or schema changes.
- Keep `null` backward compatible as restore-default; document the distinction to prevent future clients from treating it as disable.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `routes.py` | Modified | Accept empty notification-time strings. |
| `static/app.js` | Modified | Submit empty strings from cleared time inputs. |
| `tests/test_api.py` | Modified | Cover disable, persistence, and `null` restore-default behavior. |
| `tests/test_scheduler.py` | Modified | Prove API-disabled schedules do not send or dedupe. |
| `openspec/specs/local-time-notifications/spec.md` | Modified | State API/UI disabled-schedule contract. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| A client mistakes `null` for disable. | Medium | Specify and test `""` = disable; `null` = restore default. |
| Empty browser time inputs are not discoverable. | Low | Preserve current controls; defer editor UX changes. |

## Rollback Plan

Revert the validator and SPA helper changes. Existing defaults and `null` restore-default behavior remain intact; no migration or data rollback is required.

## Dependencies

- Existing empty-string persistence and scheduler semantics remain unchanged.

## Success Criteria

- [ ] A cleared time input persists as `""`, is returned by `GET /api/settings`, and disables that notification type.
- [ ] `null` continues to restore the configured default, while invalid non-empty times return 422.
- [ ] Full pytest suite passes with new regression coverage.
