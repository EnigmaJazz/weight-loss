# Proposal: Checkpoint Celebration Notifications

## Intent

Complete the gamification loop: when a reward checkpoint is newly earned (10/25/50/75/100%), the app sends a fun push notification with a message drawn from a celebration pool. Client confetti already fires on earn; the push extends the celebration to the user's device. Earn moments are currently silent server-side — the `earned_at` stamp in `_reconcile_active_rewards` is computed but never acted upon.

## Assumptions (user-confirmed)

1. **Batched**: multiple checkpoints earned in one mutation → ONE notification mentioning the top milestone percent (matches single confetti burst). No per-checkpoint pushes.
2. **Re-earn fires again**: fresh `earned_at` after regression is a new earn moment (consistent with client confetti).
3. **Settings-driven earns fire**: target/height/override changes that newly earn checkpoints celebrate; baseline-shift deletes MAY fire; revoke-only changes NEVER fire; same-event revoke+earn fires only for earned percents (set semantics — no double-fire per percent).
4. **Zero surface expansion**: `NOTIFICATION_TYPES` untouched; "checkpoint" is event-driven only. No scheduler/SW/SPA/drift-guard changes.

## Scope

### In Scope
- `newly_earned_checkpoints(before, after)` — pure set-difference diff helper in `rewards.py`
- `CELEBRATION_MESSAGES` pool in `constants.py` (style-matched, `{percent}` placeholder) + `pick_celebration(percent, rng=None)` in `notifications.py`
- `send_celebration(subscriptions, percent, vapid)` in `notifications.py` (`notif_type="checkpoint"`)
- Fire sequence in the 5 earn-capable routes: before → mutate → after → diff → fire if newly AND subscriptions exist; `request: Request` signature addition
- Tests: diff helper units, seeded-rng determinism, route earn scenarios, no-fire cases

### Out of Scope
- Per-checkpoint stacked pushes (batched by decision)
- Celebration settings UI / opt-out
- Dedupe table or persisted celebration history (`earned_at` is the dedupe)
- Scheduler integration, SW/SPA changes, `NOTIFICATION_TYPES` extension, `/api/notify/checkpoint` exposure

## Capabilities

### New Capabilities
- `checkpoint-celebrations`: celebration push on earn events — message pool + picker, diff-based earn detection, batched single send with top milestone, fire/no-fire conditions per route type

### Modified Capabilities
- None — rewards state semantics (thresholds, reconciliation, re-earning, settings keys) are unchanged; this is purely additive on top of the existing `earned_at` stamp

## Approach

Per route: `before = db.list_active_rewards(user.id)` → mutate → `after` → diff by percent → fire top percent if newly earned AND subscriptions exist. `send_to_all(..., notif_type="checkpoint")` renders its own SW slot — zero SW changes. Failed mutations (e.g. `DuplicateDateError`) never fire (ordering). All lookups user-scoped; per-user isolation preserved. No fire on: idempotent re-POST, revoke-only, non-reward settings (theme), zero subscriptions, startup reconciliation.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `routes.py` | Modified | `+request: Request` + fire sequence at 751, 783, 800, 828, 1051 |
| `rewards.py` | Modified | +`newly_earned_checkpoints` |
| `notifications.py` | Modified | +`pick_celebration`, `send_celebration` |
| `constants.py` | Modified | +`CELEBRATION_MESSAGES` |
| `tests/` | Modified | +celebration units + route earn/no-fire scenarios |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Double-fire per percent (e.g. settings churn) | Med | Set-difference semantics + `earned_at` dedupe; same-event revoke+earn fires once per percent |
| Push spam from repeated earns | Low | One batched push per mutation; revoke-only never fires |
| Contract-test churn in `test_notifications.py` | Low | `NOTIFICATION_TYPES` untouched |

## Rollback Plan

Revert fire calls in the 5 routes + the three new helpers. Celebrations are fire-and-forget with no persisted state — reverting code stops future sends. No data migration or schema change.

## Dependencies

- VAPID keys already on `app.state.vapid`; `pywebpush` already integrated. No new packages.

## Success Criteria

- [ ] Earn via upsert/edit/delete/settings/onboarding fires exactly one celebration push naming the top earned percent
- [ ] Re-earn fires; idempotent re-POST, revoke-only, non-reward settings, and zero-subscription cases fire zero pushes
- [ ] Full pytest suite + pyright pass
