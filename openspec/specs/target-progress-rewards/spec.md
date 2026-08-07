# Target Progress Rewards Specification

## Purpose

Define reversible active rewards at fixed percentages of progress from a start weight to a target weight.

## Requirements

### Requirement: Checkpoint Thresholds

The system MUST define checkpoints `10%, 25%, 50%, 75%, 100%`. For checkpoint `p`, threshold kg MUST equal `start − p × (start − target)`. Start MUST be `start_weight_override` when configured, otherwise the earliest-dated weight entry.

#### Scenario: Use earliest entry

- GIVEN earliest weight 100 kg, target 80 kg, and no override
- WHEN thresholds are calculated
- THEN the 10% and 100% thresholds MUST be 98 kg and 80 kg

#### Scenario: Use configured override

- GIVEN earliest weight 100 kg, override 110 kg, and target 80 kg
- WHEN thresholds are calculated
- THEN 110 kg MUST be used as start for every checkpoint

### Requirement: Active Reward State

A checkpoint MUST be active exactly when a start and target exist and the latest-dated weight is at or below its threshold. The system MUST return only active checkpoints and MUST NOT retain revoked-reward history.

#### Scenario: Earn checkpoints inclusively

- GIVEN thresholds at 98 kg and 95 kg
- WHEN the latest-dated weight becomes exactly 95 kg
- THEN both checkpoints MUST be active

#### Scenario: Revoke after regression

- GIVEN the 10% and 25% checkpoints are active
- WHEN the latest-dated weight becomes greater than both thresholds
- THEN both checkpoints MUST be removed from active rewards

### Requirement: Mutation Reconciliation

After every successful weight upsert or delete, the system MUST recompute start, latest-dated weight, thresholds, and the complete active checkpoint set from current entries and settings.

#### Scenario: Upsert changes latest progress

- GIVEN one or more active checkpoints
- WHEN an upsert creates or changes the latest-dated weight
- THEN the active set MUST match the recomputed thresholds and latest weight

#### Scenario: Historical upsert changes start

- GIVEN start comes from the earliest entry
- WHEN an earlier-dated entry is upserted
- THEN all thresholds and active checkpoints MUST be reconciled using the new start

#### Scenario: Delete changes governing entries

- GIVEN the earliest or latest-dated entry governs reward state
- WHEN that entry is deleted
- THEN reward state MUST be reconciled from the remaining entries, or become empty if none remain

### Requirement: Re-Earning

A revoked checkpoint MUST become active again when renewed progress places the latest-dated weight at or below its threshold. Re-earning MUST create a new local earned timestamp and MUST NOT restore prior revoked history.

#### Scenario: Re-earn after renewed progress

- GIVEN a checkpoint was earned and later revoked
- WHEN a subsequent latest-dated weight reaches its threshold again
- THEN the checkpoint MUST be active with a newly earned local timestamp

### Requirement: Authenticated Reward Isolation

`GET /api/rewards` MUST require authentication and MUST derive start weight, current weight, target, thresholds, progress, and active checkpoints solely from the authenticated user's entries and settings. An unauthenticated request MUST return status 401.

#### Scenario: Derive rewards for one user

- GIVEN users A and B have different entries and targets
- WHEN user A requests rewards
- THEN every returned reward value MUST be derived only from user A's data

#### Scenario: Reject unauthenticated reward access

- GIVEN no valid session
- WHEN rewards are requested
- THEN the API MUST respond with status 401 and disclose no reward state

### Requirement: User-Scoped Active Rewards

Persisted active rewards MUST be owned by one user. Reconciliation after weight or setting changes MUST add, revoke, or re-earn checkpoints only for the affected user; startup reconciliation MUST independently reconcile every registered user.

#### Scenario: Reconcile one user's mutation

- GIVEN users A and B have active checkpoints
- WHEN user A changes a governing weight or setting
- THEN user A's checkpoints MUST be reconciled
- AND user B's active rewards MUST remain unchanged

#### Scenario: Store the same checkpoint for two users

- GIVEN users A and B both earn the 25% checkpoint
- WHEN active rewards are persisted
- THEN each user MUST retain an independent 25% active reward

#### Scenario: Reconcile all users at startup

- GIVEN multiple users have persisted entries and settings
- WHEN application startup reconciliation runs
- THEN each user's active rewards MUST match only that user's current data

## Acceptance Criteria

- Automated tests MUST cover all five thresholds, boundary equality, regression, revocation, and re-earning.
- Upsert and delete tests MUST prove reconciliation for earliest and latest entry changes.
