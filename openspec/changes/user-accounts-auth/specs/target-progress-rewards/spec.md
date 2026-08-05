# Delta for Target Progress Rewards

## ADDED Requirements

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
