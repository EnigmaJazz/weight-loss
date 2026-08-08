# Checkpoint Celebrations Specification

## Purpose

Server-side celebration push fired when a reward checkpoint is newly earned. Earn detection is a pure set-difference over the existing `earned_at` reconciliation; delivery reuses `send_to_all` with `notif_type="checkpoint"`. No persisted state, no surface expansion.

## Requirements

### Requirement: Newly-Earned Detection

`rewards.py` MUST provide a pure, I/O-free `newly_earned_checkpoints(before, after)` returning the set-difference of active percents (`after − before`).

#### Scenario: Single earn

- GIVEN before = {10}, after = {10, 25}
- WHEN the diff is computed
- THEN it MUST return {25}

#### Scenario: Idempotent re-POST

- GIVEN before = after = {10, 25}
- WHEN the diff is computed
- THEN it MUST return the empty set

#### Scenario: Revoke-only

- GIVEN before = {10, 25}, after = {10}
- WHEN the diff is computed
- THEN it MUST return the empty set

#### Scenario: Same-event revoke and earn

- GIVEN before = {25}, after = {25} (revoked then re-earned)
- WHEN the diff is computed
- THEN it MUST return the empty set (no double-fire per percent)

### Requirement: Celebration Message Pool and Picker

`constants.py` MUST define `CELEBRATION_MESSAGES`: ≥3 distinct bodies, style-matched to `NOTIFICATION_MESSAGES`, each with a `{percent}` placeholder. `notifications.py` MUST provide `pick_celebration(percent, rng=None)` returning `(title, body)` with `{percent}` interpolated; a seeded `rng` MUST select deterministically, mirroring `pick_message`.

#### Scenario: Seeded determinism

- GIVEN a fixed `random.Random` seed
- WHEN `pick_celebration` is called twice with the same percent and seed
- THEN both calls MUST return identical (title, body)

#### Scenario: Placeholder interpolation

- GIVEN a pool body `"You hit {percent}%!"`
- WHEN `pick_celebration(25)` runs
- THEN the body MUST contain `25%` and MUST NOT contain `{percent}`

### Requirement: Celebration Push Delivery

`send_celebration(subscriptions, percent, vapid)` MUST call `send_to_all(..., notif_type="checkpoint")` with the picked message. When multiple percents are newly earned in one mutation, the system MUST send exactly ONE push naming the TOP (highest) percent.

#### Scenario: Batched top percent

- GIVEN newly earned {10, 25, 50} and ≥1 subscription
- WHEN the celebration is delivered
- THEN exactly one push MUST be sent naming percent 50

#### Scenario: Tag and pool membership

- GIVEN a celebration push is delivered
- THEN `notif_type` MUST equal `checkpoint` AND the body MUST be drawn from `CELEBRATION_MESSAGES`

### Requirement: Earn-Event Fire Points

The 5 earn-capable routes (weight upsert, edit, delete; settings update; onboarding) MUST capture `before = list_active_rewards(user.id)`, mutate, capture `after`, diff, and fire only when the diff is non-empty AND ≥1 subscription exists. Fire MUST occur AFTER a successful mutation; a failed mutation MUST NOT fire. Each route MUST add `request: Request`.

#### Scenario: Upsert single earn

- GIVEN 0 active, a weight reaching the 10% threshold, and ≥1 subscription
- WHEN the user upserts that weight
- THEN exactly one push naming 10 MUST fire

#### Scenario: Settings earn; theme no-fire

- GIVEN a target/height change newly earns 25% with ≥1 subscription
- WHEN the user updates settings
- THEN one push naming 25 MUST fire
- AND a settings update of only `theme` MUST fire zero pushes

#### Scenario: Onboarding first-entry earn

- GIVEN onboarding's first weight earns ≥1 checkpoint with ≥1 subscription
- WHEN the user completes onboarding
- THEN exactly one push naming the top earned percent MUST fire

#### Scenario: Delete baseline-shift earn

- GIVEN deleting the earliest entry shifts the baseline and newly earns a checkpoint with ≥1 subscription
- WHEN the user deletes that entry
- THEN one push naming the top earned percent MUST fire
- AND a revoke-only delete MUST fire zero pushes

#### Scenario: Failed mutation no-fire

- GIVEN an edit collides on date (409) with ≥1 subscription
- WHEN the request is handled
- THEN zero pushes MUST fire

### Requirement: Re-Earn Refire

A checkpoint re-earned after revocation (fresh `earned_at`) MUST fire a celebration push again.

#### Scenario: Refire after recovery

- GIVEN 25% was earned then revoked, and progress recovers past 25% with ≥1 subscription
- WHEN the user upserts the recovering weight
- THEN a push naming 25 MUST fire again

### Requirement: No-Fire and Isolation Guards

Zero subscriptions MUST NOT fire and MUST NOT write dedupe side effects. Earn detection MUST be per-user isolated. `NOTIFICATION_TYPES`, scheduler, service worker, SPA, and drift-guard MUST remain unchanged. No `/api/notify/checkpoint` endpoint MUST be exposed.

#### Scenario: Zero subscriptions

- GIVEN a newly earned checkpoint and zero subscriptions
- WHEN the mutation completes
- THEN zero pushes MUST be attempted AND no dedupe key MUST be written

#### Scenario: Per-user isolation

- GIVEN user A earns a checkpoint and user B has ≥1 subscription
- WHEN user A's mutation fires
- THEN only user A's subscriptions MUST be notified

### Requirement: Test Coverage

Every code path MUST have a regression test via the `stub_push` fixture: upsert earn (single + batched), idempotent/revoke no-fire, re-earn refire, settings earn + theme no-fire, onboarding first-entry earn, delete baseline-shift earn, per-user isolation, zero-subscription no-fire, and pure-unit tables for the diff helper and `pick_celebration` determinism.

#### Scenario: stub_push capture

- GIVEN a celebration push is fired
- THEN `stub_push` MUST record `notif_type == "checkpoint"`, a body in `CELEBRATION_MESSAGES`, and the top percent named for batches
